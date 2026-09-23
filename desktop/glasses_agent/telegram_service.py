"""The AI's own Telegram user account, driven with Telethon.

Three members share one group:
  * you (OWNER)      the AI answers you
  * the glasses bot  the AI reads its photos and #status lines
  * the AI account   (this code)
Anything posted by anyone else is ignored. Senders are matched by numeric user id,
resolved once from @usernames, because display names can be copied by anyone.
"""
from __future__ import annotations

import asyncio
import logging
import platform
import re
from pathlib import Path

import httpx
from telethon import TelegramClient, events, utils
from telethon.errors import RPCError
from telethon.tl.functions.messages import AddChatUserRequest, CreateChatRequest, ExportChatInviteRequest

from .config import Settings, State

log = logging.getLogger(__name__)

STATUS_RE = re.compile(r"(\w+)=(\S+)")
HELP = (
    "What I respond to in this group:\n"
    "/look [question] — the glasses take a photo now and I answer the question from it\n"
    "/ping — check that the glasses are online\n"
    "Anything else — normal chat. I remember what the glasses have shown me today.\n"
    "Press the glasses' button any time to send me a frame."
)


def make_client(settings: Settings) -> TelegramClient:
    return TelegramClient(
        str(settings.session_path), settings.tg_api_id, settings.tg_api_hash,
        device_model="Loupe desktop", system_version=platform.platform(terse=True), app_version="1.0",
    )


async def bot_username(token: str) -> str:
    async with httpx.AsyncClient(timeout=10) as http:
        r = await http.get(f"https://api.telegram.org/bot{token}/getMe")
    data = r.json()
    if not data.get("ok"):
        raise _SetupError("GLASSES_BOT_TOKEN was rejected by Telegram. Copy it again from @BotFather.")
    return data["result"]["username"]


def display_name(entity) -> str:
    first = getattr(entity, "first_name", "") or ""
    last = getattr(entity, "last_name", "") or ""
    name = f"{first} {last}".strip() or getattr(entity, "title", "") or ""
    user = getattr(entity, "username", None)
    return f"{name} (@{user})" if user else name


class TelegramService:
    def __init__(self, core):
        self.core = core
        self.settings: Settings = core.settings
        self.state: State = core.state
        self.client: TelegramClient | None = None  # created once API credentials exist
        self.ready = False
        self.me_id: int | None = None
        self.owner_id: int | None = None
        self.bot_id: int | None = None
        self.bot_username: str = ""
        self.group_id: int | None = self.state.get("group_id")

    # ------------------------------------------------------------ startup

    async def run(self) -> None:
        st = self.core.status
        if not (self.settings.tg_api_id and self.settings.tg_api_hash):
            st.set("telegram", "off", "Fill TG_API_ID and TG_API_HASH in desktop/.env")
            return
        self.client = make_client(self.settings)
        self.client.add_event_handler(self._on_message, events.NewMessage(incoming=True))
        while True:
            try:
                await self._connect_and_listen()
            except asyncio.CancelledError:
                raise
            except _SetupError as e:
                st.set("telegram", "error", str(e))
                return
            except Exception as e:  # noqa: BLE001 — network drops: retry
                self.ready = False
                st.set("telegram", "error", f"Disconnected ({e.__class__.__name__}). Retrying in 30 s.")
                await asyncio.sleep(30)

    async def _connect_and_listen(self) -> None:
        st = self.core.status
        await self.client.connect()
        if not await self.client.is_user_authorized():
            raise _SetupError("The AI account isn't logged in. Run: python -m glasses_agent login")

        me = await self.client.get_me()
        self.me_id = me.id
        self.state.set(me_id=me.id, me_name=display_name(me))

        try:
            owner = await self.client.get_entity(_as_peer(self.settings.owner))
        except (ValueError, RPCError) as e:
            raise _SetupError(f"Can't find OWNER {self.settings.owner!r} on Telegram. Use your @username.") from e
        self.owner_id = owner.id
        self.state.set(owner_id=owner.id, owner_name=display_name(owner))

        if not self.settings.glasses_bot_token:
            raise _SetupError("GLASSES_BOT_TOKEN is empty. Create the bot with @BotFather first.")
        self.bot_username = await bot_username(self.settings.glasses_bot_token)
        bot = await self.client.get_entity(self.bot_username)
        self.bot_id = bot.id
        self.state.set(bot_id=bot.id, bot_username=self.bot_username)

        if not self.group_id:
            await self._create_group(owner, bot)

        self.ready = True
        st.set("telegram", "ok", f"{display_name(me)} in “{self.settings.group_title}”")
        await self.send_ping()
        await self.client.run_until_disconnected()
        self.ready = False

    async def _create_group(self, owner, bot) -> None:
        res = await self.client(CreateChatRequest(users=[bot], title=self.settings.group_title))
        chat = getattr(res, "updates", res).chats[0]
        self.group_id = utils.get_peer_id(chat)
        self.state.set(group_id=self.group_id)
        try:
            await self.client(AddChatUserRequest(chat_id=chat.id, user_id=owner, fwd_limit=0))
        except RPCError:
            # Their privacy settings block being added to groups; send an invite link instead.
            invite = await self.client(ExportChatInviteRequest(peer=chat))
            await self.client.send_message(owner, f"I made the {self.settings.group_title} group for your "
                                                  f"glasses. Join here: {invite.link}")
        await self.client.send_message(self.group_id, HELP)
        log.info("created group %s (%s)", self.settings.group_title, self.group_id)

    # ------------------------------------------------------------ incoming

    async def _on_message(self, event) -> None:
        sender = event.sender_id
        in_group = event.chat_id == self.group_id
        from_owner_dm = event.is_private and sender == self.owner_id
        if not (in_group or from_owner_dm):
            return

        if sender == self.bot_id and in_group:
            await self._from_glasses(event)
        elif sender == self.owner_id:
            await self._from_owner(event)
        # Everyone else, including other bots and people added to the group, is ignored.

    async def _from_glasses(self, event) -> None:
        text = event.raw_text or ""
        if text.startswith("#status"):
            self.core.glasses_heard(dict(STATUS_RE.findall(text)))
            return
        if not _is_image(event.message):
            return
        reason = text.split()[1] if text.startswith("#capture") and len(text.split()) > 1 else "button"
        jpeg = await event.message.download_media(file=bytes)
        async with self.client.action(event.chat_id, "typing"):
            cap = await self.core.handle_frame(jpeg, source="telegram", reason=reason)
        if cap:
            await event.reply(cap.answer)

    async def _from_owner(self, event) -> None:
        text = (event.raw_text or "").strip()
        if _is_image(event.message):
            jpeg = await event.message.download_media(file=bytes)
            cap = await self.core.handle_frame(jpeg, source="telegram", reason="owner-photo",
                                               question=text)
            if cap:
                await event.reply(cap.answer)
            return

        cmd = text.split()[0].split("@")[0].lower() if text.startswith("/") else ""
        if cmd == "/look":
            question = text.partition(" ")[2].strip() or "What am I looking at?"
            await event.reply("Looking…")
            await self.core.request_snapshot(question)
        elif cmd == "/ping":
            await self.send_ping()
            await event.reply("Pinged the glasses. Their #status line should appear in a few seconds.")
        elif cmd in ("/help", "/start"):
            await event.reply(HELP)
        elif text:
            async with self.client.action(event.chat_id, "typing"):
                answer = await self.core.chat(text)
            await event.reply(answer)

    # ------------------------------------------------------------ outgoing

    async def send_snap(self) -> None:
        # Addressed to the bot explicitly so it arrives even with group privacy mode on.
        await self.client.send_message(self.group_id, f"/snap@{self.bot_username}")

    async def send_ping(self) -> None:
        if self.group_id and self.bot_username:
            await self.client.send_message(self.group_id, f"/ping@{self.bot_username}")

    async def send_group(self, text: str, photo: Path | None = None) -> None:
        if photo:
            await self.client.send_file(self.group_id, photo, caption=text[:1000])
        else:
            await self.client.send_message(self.group_id, text)


class _SetupError(RuntimeError):
    """A problem the user has to fix; retrying won't help."""


def _as_peer(value: str):
    value = value.strip()
    return int(value) if value.lstrip("-").isdigit() else value


def _is_image(message) -> bool:
    if message.photo:
        return True
    doc = message.document
    return bool(doc and (doc.mime_type or "").startswith("image/"))


async def interactive_login(settings: Settings) -> None:
    """First-time sign-in for the AI account. Telegram texts a code to that account."""
    client = make_client(settings)
    await client.start(phone=settings.tg_phone or None)
    me = await client.get_me()
    State().set(me_id=me.id, me_name=display_name(me))
    print(f"Logged in as {display_name(me)} (id {me.id}). The session is saved in {settings.session_path}.session")
    print("Keep that file private: it works like a password for the AI's account.")
    await client.disconnect()

