import { t } from "../i18n.js";
import { esc, playerName, seatColor } from "./util.js";

export function topbar(view, store) {
  const players = view.players
    .map(
      (p) => `<span class="player ${p.seat === view.current ? "current" : ""}">
        <span class="dot" style="background:${seatColor(p.seat)}"></span> ${esc(p.name)} ${p.vp}</span>`,
    )
    .join("");
  const seatOptions = view.players
    .map((p) => `<option value="${p.seat}" ${p.seat === view.you ? "selected" : ""}>${esc(p.name)}</option>`)
    .join("");
  return `
    <div class="box topbar">
      <span><span class="label">${t("ui.topbar.game")}</span> <span class="code">${esc(view.game_id)}</span></span>
      <span class="label">${t("ui.topbar.round", { round: view.round })}</span>
      <span><span class="label">${t("ui.topbar.turn")}</span>
        <span class="dot" style="background:${seatColor(view.current)}"></span> ${esc(playerName(view, view.current))}</span>
      <span class="players">${players}</span>
      <span class="controls">
        <label>${t("ui.topbar.viewing_as")} <select data-change="seat">${seatOptions}</select></label>
        <label><input type="checkbox" data-change="follow" ${store.follow ? "checked" : ""}> ${t("ui.topbar.follow_turn")}</label>
        <button data-action="new-game">${t("ui.topbar.new_game")}</button>
      </span>
    </div>`;
}
