"""Gmail backup path. Each device has its own Gmail account:

  glasses Gmail --(frame by email when Telegram fails)--> AI Gmail inbox  (polled here over IMAP)
  AI Gmail      --(reply when Telegram is down on this side)--> OWNER_EMAIL

Both accounts need 2-Step Verification plus an App Password (myaccount.google.com/apppasswords).
"""
from __future__ import annotations

import asyncio
import email
import imaplib
import logging
import smtplib
from email.message import EmailMessage
from email.utils import parseaddr
from pathlib import Path

log = logging.getLogger(__name__)


class GmailBackup:
    def __init__(self, core):
        self.core = core
        self.s = core.settings

    async def run(self) -> None:
        st = self.core.status
        if not self.s.gmail_enabled:
            st.set("gmail", "off", "Backup off: fill AI_GMAIL, AI_GMAIL_APP_PASSWORD and GLASSES_GMAIL")
            return
        while True:
            try:
                frames = await asyncio.to_thread(self._fetch_frames)
                st.set("gmail", "ok", f"watching {self.s.ai_gmail} for frames from {self.s.glasses_gmail}")
                for reason, jpeg in frames:
                    cap = await self.core.handle_frame(jpeg, source="gmail", reason=reason)
                    if cap:
                        await self.core.notify_owner(f"(arrived by email backup)\n{cap.answer}",
                                                     self.core.memory.path(cap))
            except imaplib.IMAP4.error as e:
                st.set("gmail", "error", f"Gmail refused the login for {self.s.ai_gmail}: {e}. "
                                         "Use an App Password, not the normal password.")
            except OSError as e:
                st.set("gmail", "warn", f"Can't reach imap.gmail.com ({e.__class__.__name__}). Retrying.")
            await asyncio.sleep(self.s.gmail_poll_seconds)

    def _fetch_frames(self) -> list[tuple[str, bytes]]:
        out: list[tuple[str, bytes]] = []
        with imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=30) as imap:
            imap.login(self.s.ai_gmail, self.s.ai_gmail_app_password)
            imap.select("INBOX")
            _, data = imap.search(None, "UNSEEN", "FROM", f'"{self.s.glasses_gmail}"')
            for num in data[0].split():
                _, parts = imap.fetch(num, "(RFC822)")  # marks the mail as read
                msg = email.message_from_bytes(parts[0][1])
                # The search matches the From header; re-check the address itself.
                if parseaddr(msg.get("From", ""))[1].lower() != self.s.glasses_gmail.lower():
                    continue
                subject = msg.get("Subject", "")
                reason = subject.rsplit(" ", 1)[-1] if "[loupe] capture" in subject else "button"
                for part in msg.walk():
                    if part.get_content_maintype() == "image":
                        payload = part.get_payload(decode=True)
                        if payload:
                            out.append((reason, payload))
        return out

    async def email_owner(self, subject: str, text: str, photo: Path | None = None) -> None:
        if not (self.s.gmail_enabled and self.s.owner_email):
            log.warning("Telegram is down and OWNER_EMAIL is empty; this reply was only saved locally")
            return
        msg = EmailMessage()
        msg["From"] = self.s.ai_gmail
        msg["To"] = self.s.owner_email
        msg["Subject"] = subject
        msg.set_content(text)
        if photo and photo.exists():
            msg.add_attachment(photo.read_bytes(), maintype="image", subtype="jpeg", filename=photo.name)

        def send():
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
                smtp.login(self.s.ai_gmail, self.s.ai_gmail_app_password)
                smtp.send_message(msg)

        await asyncio.to_thread(send)
