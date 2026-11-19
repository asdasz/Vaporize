// Overlay listing a public pile (a player's discard pile or removed cards), opened by clicking the pile.
import { t } from "../i18n.js";
import { icon } from "../icons.js";
import { handCard } from "./card.js";
import { esc } from "./util.js";

export function pileOverlay(view, store) {
  const open = store.pileView;
  if (!open) return "";
  const p = view.players[open.seat];
  if (!p) return "";
  const cards = open.which === "removed" ? p.removed : p.discard;
  const title = t(`ui.seat.${open.which}_title`, { name: p.name, count: cards.length });
  const body = cards.length
    ? [...cards].reverse().map((c) => handCard(c, { still: true })).join("")
    : `<span class="muted">${t("ui.remove.empty")}</span>`;
  return `
    <div class="remove-overlay" data-action="close-pile-backdrop">
      <div class="remove-dialog" data-stop>
        <div class="remove-head">
          <h3>${esc(title)}</h3>
          <button data-action="close-pile">${icon("cancel")}${t("ui.seat.close")}</button>
        </div>
        <div class="muted">${t("ui.seat.top_first")}</div>
        <div class="remove-cards">${body}</div>
      </div>
    </div>`;
}
