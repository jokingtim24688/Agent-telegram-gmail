// Loupe dashboard: polls the local API and renders the contact sheet.

const $ = (sel, root = document) => root.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const api = async (path, body) => {
  const res = await fetch(path, body === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path} answered ${res.status}`);
  return res.json();
};

let toastTimer;
function toast(text, state = "ok") {
  const el = $("#toast");
  el.textContent = text;
  el.dataset.s = state;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.hidden = true), state === "error" ? 9000 : 4500);
}

function ago(ts, now) {
  if (!ts) return "never";
  const s = Math.max(0, Math.round(now - ts));
  if (s < 90) return `${s}s ago`;
  if (s < 5400) return `${Math.round(s / 60)} min ago`;
  return `${Math.round(s / 3600)} h ago`;
}

// ------------------------------------------------------------------ status

let lastCount = -1;

async function refreshStatus() {
  let st;
  try {
    st = await api("/api/status");
  } catch {
    for (const li of document.querySelectorAll("#signals li")) {
      $(".dot", li).dataset.s = "error";
      $("span", li).textContent = "dashboard lost contact with Loupe";
    }
    return;
  }

  for (const li of document.querySelectorAll("#signals li")) {
    const c = st.components[li.dataset.k] || { state: "off", detail: "" };
    $(".dot", li).dataset.s = c.state;
    let detail = c.detail;
    if (li.dataset.k === "glasses" && st.glasses.seen) {
      detail = `${c.state === "ok" ? "online" : "quiet"}, ${ago(st.glasses.seen, st.now)}`;
      if (st.glasses.info.rssi) detail += `, ${st.glasses.info.rssi} dBm`;
    } else if (li.dataset.k === "glasses" && c.state === "off") {
      detail = "not heard from yet";
    }
    $("span", li).textContent = detail;
    li.title = c.detail;
  }

  const busy = $("#busy");
  busy.hidden = !st.busy;
  if (st.busy) $("span", busy).textContent = `${st.busy}…`;

  const pending = $("#pending");
  pending.hidden = !st.pending_look;
  if (st.pending_look) pending.innerHTML = `Waiting for the glasses to answer <b>“${esc(st.pending_look)}”</b>`;

  $("#setup").hidden = st.problems.length === 0;
  $("#problems").innerHTML = st.problems.map((p) => `<li>${esc(p)}</li>`).join("");

  const p = st.people;
  const who = (v, fallback) => v ? esc(v) : `<span class="ignored">${fallback}</span>`;
  $("#listeners").innerHTML = `
    <div><dt>The AI answers</dt><dd>${who(p.owner, "you, once OWNER is set and the AI is logged in")}</dd>
      <dd>${who(p.glasses_bot && "@" + p.glasses_bot, "the glasses bot, once its token is set")}</dd></div>
    <div><dt>The glasses obey</dt><dd>${who(p.ai, "the AI account, after python -m glasses_agent login")}</dd></div>
    <div><dt>Group</dt><dd>${who(p.group, "created automatically on first run")}</dd>
      <dd class="ignored">Anyone else in the group is ignored. Senders are matched by Telegram user ID, not display name.</dd></div>`;

  if (st.captures !== lastCount) {
    lastCount = st.captures;
    refreshSheet();
  }
}

// ------------------------------------------------------------------ contact sheet

const seen = new Set();
let firstSheetLoad = true;

async function refreshSheet() {
  const q = $("#find").value.trim();
  const { items } = await api(`/api/captures?limit=60&q=${encodeURIComponent(q)}`);
  const sheet = $("#sheet");
  const empty = $("#empty");

  $("#count").textContent = q ? `${items.length} matching` : lastCount > 0 ? `${lastCount} frames` : "";

  if (!items.length) {
    sheet.innerHTML = "";
    empty.hidden = false;
    empty.innerHTML = q
      ? `<h3>No frame mentions “${esc(q)}”</h3><p>The search reads what the AI wrote about each photo, so use the word it would have used: “receipt” rather than “paper”.</p>`
      : `<h3>Nothing on the sheet yet</h3><p>Press the button on the glasses, or type a question above and hit <kbd>Look now</kbd>. The glasses take the shot, the AI answers in your Telegram group, and the frame develops here.</p>`;
    return;
  }
  empty.hidden = true;

  sheet.innerHTML = items.map((c, i) => {
    const isNew = !firstSheetLoad && !seen.has(c.id);
    const asked = c.question ? `<p class="asked">“${esc(c.question)}”</p>` : "";
    const tags = [
      c.source === "gmail" ? `<span class="tag tag--mail">email backup</span>` : "",
      c.reason === "owner-photo" ? `<span class="tag">your photo</span>` : "",
    ].join("");
    return `<li class="print${i === 0 && !q ? " print--lead" : ""}${isNew ? " print--developing" : ""}" data-id="${c.id}">
      <a href="${esc(c.image)}" target="_blank" rel="noopener"><img src="${esc(c.image)}" alt="Frame ${c.id}" loading="lazy"></a>
      <div class="edge"><span class="frame-no">${c.id}</span><time>${esc(c.when)}</time>${tags}</div>
      <div class="caption">${asked}<p>${esc(c.answer)}</p></div>
    </li>`;
  }).join("");
  items.forEach((c) => seen.add(c.id));
  firstSheetLoad = false;
}

let findTimer;
$("#find").addEventListener("input", () => {
  clearTimeout(findTimer);
  findTimer = setTimeout(refreshSheet, 250);
});

$("#ask").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $(".btn--shutter");
  btn.disabled = true;
  try {
    const r = await api("/api/look", { question: $("#question").value });
    toast(r.detail, r.ok ? "ok" : "error");
    if (r.ok) $("#question").value = "";
  } catch (err) {
    toast(`Couldn't ask the glasses: ${err.message}`, "error");
  } finally {
    btn.disabled = false;
    refreshStatus();
  }
});

// ------------------------------------------------------------------ model fit

async function refreshModels() {
  let hw;
  try {
    hw = await api("/api/hardware");
  } catch {
    $("#hw").textContent = "Couldn't read this machine's hardware.";
    return;
  }
  const h = hw.hardware;
  $("#hw").textContent = `${h.gpu}\n${h.unified ? "Unified memory" : "VRAM"} ${h.memory_gb} GB, ${h.usable_gb} GB usable for a model`;
  $("#hw").style.whiteSpace = "pre-line";

  const current = hw.models.find((m) => m.name === hw.current) || { size_gb: 0, name: hw.current };
  const cap = Math.max(h.usable_gb, current.size_gb + hw.overhead_gb, 0.1);
  const gauge = $("#gauge");
  $(".gauge-model", gauge).style.width = `${(current.size_gb / cap) * 100}%`;
  $(".gauge-room", gauge).style.width = `${(hw.overhead_gb / cap) * 100}%`;
  const spill = current.size_gb + hw.overhead_gb > h.usable_gb;
  gauge.classList.toggle("gauge--spill", spill);
  $("#gauge-legend").textContent = spill
    ? `${current.name} needs ${(current.size_gb + hw.overhead_gb).toFixed(1)} GB, so part of it runs on the CPU. Expect slow answers.`
    : `${current.name}: ${current.size_gb} GB of weights plus ${hw.overhead_gb} GB working room fits on the GPU.`;

  $("#models").innerHTML = hw.models.map((m) => {
    const sight = m.vision === false ? "text only" : m.vision ? "sees images" : "";
    const fit = m.fits ? "" : `<span class="fit-no"> won't fit on GPU</span>`;
    let action;
    if (m.name === hw.current) action = `<span class="pick">In use</span>`;
    else if (m.installed) action = `<button class="btn btn--quiet" data-use="${esc(m.name)}">Use this</button>`;
    else action = `<code data-copy="ollama pull ${esc(m.name)}" title="Click to copy">ollama pull ${esc(m.name)}</code>`;
    const rec = m.recommended ? " (best fit here)" : "";
    return `<li class="${m.name === hw.current ? "current" : ""}">
      <span class="name">${esc(m.name)}${rec}</span><span class="size">${m.size_gb} GB</span>
      <span class="note">${esc(sight)}${sight && m.note ? ". " : ""}${esc(m.note)}${fit}</span>
      <span class="actions">${action}</span></li>`;
  }).join("");
  if (!hw.ollama_up) {
    $("#gauge-legend").textContent += " Ollama isn't running, so installed models can't be listed.";
  }
}

$("#models").addEventListener("click", async (e) => {
  const use = e.target.closest("[data-use]");
  const copy = e.target.closest("[data-copy]");
  if (use) {
    const r = await api("/api/model", { name: use.dataset.use });
    toast(r.detail);
    refreshModels();
  } else if (copy) {
    try {
      await navigator.clipboard.writeText(copy.dataset.copy);
      toast(`Copied. Paste it into a terminal: ${copy.dataset.copy}`);
    } catch {
      toast(copy.dataset.copy);
    }
  }
});

// ------------------------------------------------------------------ board

function boardLog(text) {
  const log = $("#board-log");
  log.hidden = false;
  log.textContent = text;
}

async function refreshPorts() {
  const { ports } = await api("/api/ports");
  const sel = $("#port");
  const prev = sel.value;
  sel.innerHTML = ports.length
    ? ports.map((p) => `<option value="${esc(p.device)}">${esc(p.device)}${p.likely_glasses ? " (glasses)" : ""} ${esc(p.description)}</option>`).join("")
    : `<option value="">No USB ports. Plug the glasses in.</option>`;
  if (prev && ports.some((p) => p.device === prev)) sel.value = prev;
}

async function boardAction(button, fn) {
  button.disabled = true;
  try {
    await fn();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    button.disabled = false;
  }
}

$("#refresh-ports").addEventListener("click", (e) => boardAction(e.currentTarget, refreshPorts));

$("#board").addEventListener("submit", (e) => {
  e.preventDefault();
  boardAction(e.submitter, async () => {
    const wifi = [...document.querySelectorAll(".wifi-row")].map((row) => ({
      ssid: $("[name=ssid]", row).value.trim(),
      password: $("[name=password]", row).value,
    })).filter((w) => w.ssid);
    const r = await api("/api/provision", { port: $("#port").value, wifi, btn_pin: Number($("#btn-pin").value) });
    toast(r.detail, r.ok ? "ok" : "error");
    if (r.ok) document.querySelectorAll(".wifi-row [name=password]").forEach((i) => (i.value = ""));
  });
});

$("#board-status").addEventListener("click", (e) => boardAction(e.currentTarget, async () => {
  const r = await api("/api/board-status", { port: $("#port").value });
  if (!r.ok) return toast(r.detail, "error");
  const b = r.board;
  boardLog([
    `firmware     ${b.fw}`,
    `provisioned  ${b.configured ? "yes" : "no, press Write to glasses"}`,
    `camera       ${b.camera ? "ok" : "not detected. Check the camera ribbon is seated"}`,
    `wifi         ${b.wifi ? `${b.wifi} (${b.rssi} dBm)` : "not connected"}`,
    `email backup ${b.gmail_backup ? "configured" : "off"}`,
    `last send    ${b.last_send}`,
    `button pin   GPIO ${b.btn_pin}`,
  ].join("\n"));
}));

$("#flash").addEventListener("click", (e) => boardAction(e.currentTarget, async () => {
  boardLog("Building and uploading. The first build downloads the ESP32 toolchain and can take several minutes…");
  const r = await api("/api/flash", { port: $("#port").value || null });
  boardLog(r.output || r.detail);
  toast(r.detail, r.ok ? "ok" : "error");
}));

$("#ping").addEventListener("click", (e) => boardAction(e.currentTarget, async () => {
  const r = await api("/api/ping", {});
  toast(r.detail, r.ok ? "ok" : "error");
}));

// ------------------------------------------------------------------ start

refreshStatus();
refreshModels();
refreshPorts().catch(() => {});
setInterval(refreshStatus, 3000);
setInterval(refreshModels, 30000);
