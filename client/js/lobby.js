// Start screen (Host game / Join game / local test), the host & join forms and the room lobby.
import { t } from "./i18n.js";

const esc = (value) =>
  String(value).replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);

// The last name you used, to fill in the forms (a convenience only).
function savedName() {
  try {
    return localStorage.getItem("vaporize.name") || "";
  } catch {
    return "";
  }
}

export function rememberName(name) {
  try {
    localStorage.setItem("vaporize.name", name);
  } catch {
    /* storage unavailable */
  }
}

const classOptions = (classes, selected) =>
  classes.map((c) => `<option value="${c}" ${c === selected ? "selected" : ""}>${t(`classes.${c}.name`)}</option>`).join("");

const notice = (key) => (key ? `<div class="chip error lobby-notice">${t(key)}</div>` : "");

export function renderStart(root, { onHost, onJoin, onLocal, noticeKey = null }) {
  root.innerHTML = `
    <div class="setup lobby">
      <h1>${t("ui.app.title")}</h1>
      ${notice(noticeKey)}
      <div class="label">${t("ui.lobby.heading")}</div>
      <div class="buttons">
        <button class="big primary" data-go="host">${t("ui.lobby.host")}</button>
        <button class="big" data-go="join">${t("ui.lobby.join")}</button>
      </div>
      <button class="link" data-go="local">${t("ui.lobby.local")}</button>
    </div>`;
  root.onclick = (event) => {
    const go = event.target.closest("[data-go]")?.dataset.go;
    if (go === "host") onHost();
    else if (go === "join") onJoin();
    else if (go === "local") onLocal();
  };
  root.onchange = null;
  root.onsubmit = null;
}

// Host: name + class. Join: code + name + class. `onSubmit` returns a promise; errors show in the form.
export function renderPlayerForm(root, { mode, classes, code = "", onSubmit, onBack, noticeKey = null }) {
  const joining = mode === "join";
  root.innerHTML = `
    <form class="setup lobby lobby-form" autocomplete="off">
      <h1>${t(joining ? "ui.lobby.join" : "ui.lobby.host")}</h1>
      ${notice(noticeKey)}
      ${joining ? `<label>${t("ui.lobby.code")}<input name="code" value="${esc(code)}" maxlength="6" required placeholder="ABC234" class="code-input"></label>` : ""}
      <label>${t("ui.lobby.name")}<input name="name" value="${esc(savedName())}" maxlength="20" placeholder="${t("ui.lobby.name_placeholder")}"></label>
      <label>${t("ui.lobby.class")}<select name="class_id">${classOptions(classes, classes[joining ? Math.min(1, classes.length - 1) : 0])}</select></label>
      <div class="error-line" data-error></div>
      <div class="buttons">
        <button type="button" data-go="back">${t("ui.lobby.back")}</button>
        <button type="submit" class="primary">${t(joining ? "ui.lobby.join_button" : "ui.lobby.host_button")}</button>
      </div>
    </form>`;
  const form = root.querySelector("form");
  form.querySelector(joining && !code ? "[name=code]" : "[name=name]").focus();
  root.onclick = (event) => {
    if (event.target.closest("[data-go=back]")) onBack();
  };
  root.onchange = null;
  root.onsubmit = async (event) => {
    event.preventDefault();
    const data = new FormData(form);
    const button = form.querySelector("[type=submit]");
    button.disabled = true;
    try {
      await onSubmit({
        code: String(data.get("code") || "").trim().toUpperCase(),
        name: String(data.get("name") || "").trim(),
        classId: String(data.get("class_id")),
      });
    } catch (err) {
      form.querySelector("[data-error]").textContent = t(err.key || "ui.errors.connection");
      button.disabled = false;
    }
  };
}

// The room before the game starts: share link, players (2-4), the host's Start button.
export function renderLobby(root, room, { onStart, onLeave, onClass, onCopy, copied = false, errorKey = null }) {
  const link = `${location.origin}${location.pathname}?room=${room.code}`;
  const host = room.players.find((p) => p.host);
  const seats = Array.from({ length: room.max_players }, (_, i) => room.players[i] || null)
    .map((p, i) => {
      if (!p) return `<li class="seat-row empty"><span class="dot" style="background:var(--seat-${i})"></span>${t("ui.lobby.empty_seat")}</li>`;
      const cls = p.you
        ? `<select data-class>${classOptions(room.classes, p.class_id)}</select>`
        : `<span class="muted">${t(`classes.${p.class_id}.name`)}</span>`;
      return `<li class="seat-row ${p.you ? "you" : ""}"><span class="dot" style="background:var(--seat-${i})"></span>
        <b>${esc(p.name)}</b>${p.host ? `<span class="badge">${t("ui.lobby.host_badge")}</span>` : ""}${p.you ? `<span class="badge you">${t("ui.lobby.you")}</span>` : ""}
        <span class="seat-class">${cls}</span></li>`;
    })
    .join("");
  const enough = room.players.length >= room.min_players;
  const footer = room.host
    ? `<button class="big primary" data-go="start" ${enough ? "" : "disabled"}>${t("ui.lobby.start", { count: room.players.length })}</button>
       <div class="muted">${t(enough ? "ui.lobby.start_hint" : "ui.lobby.need_players")}</div>`
    : `<div class="muted">${t("ui.lobby.waiting_host", { name: esc(host ? host.name : "") })}</div>`;
  root.innerHTML = `
    <div class="setup lobby lobby-room">
      <h1>${t("ui.lobby.room_title")} <span class="code">${room.code}</span></h1>
      ${notice(errorKey)}
      <div class="share">
        <div class="label">${t("ui.lobby.share")}</div>
        <div class="share-row"><input readonly value="${esc(link)}" data-link><button data-go="copy">${t(copied ? "ui.lobby.copied" : "ui.lobby.copy")}</button></div>
      </div>
      <div class="label">${t("ui.lobby.players", { count: room.players.length, max: room.max_players })}</div>
      <ul class="seat-list">${seats}</ul>
      <div class="lobby-footer">${footer}</div>
      <button class="link" data-go="leave">${t(room.host ? "ui.lobby.close" : "ui.lobby.leave")}</button>
    </div>`;
  root.onclick = (event) => {
    const go = event.target.closest("[data-go]")?.dataset.go;
    if (go === "start") onStart();
    else if (go === "leave") onLeave();
    else if (go === "copy") onCopy(link);
    else if (event.target.closest("[data-link]")) event.target.select();
  };
  root.onchange = (event) => {
    if (event.target.closest("[data-class]")) onClass(event.target.value);
  };
  root.onsubmit = null;
}
