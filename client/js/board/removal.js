// Card removal overlay (Hearthstone-style): removable cards in the middle of the screen, grouped by
// where they are. Peek hides the overlay to look at the table. Every removal asks to confirm.
import { t } from "../i18n.js";
import { icon } from "../icons.js";
import { handCard } from "./card.js";
import { cardName, esc } from "./util.js";

function section(title, cards, removable, emptyKey, note = "") {
  const body = cards.length
    ? cards
        .map((c) => {
          const ok = removable.has(c.uid);
          return `<div class="remove-pick ${ok ? "" : "locked"}" ${ok ? `data-action="pick-remove" data-uid="${c.uid}"` : ""}>${handCard(c, { still: true })}</div>`;
        })
        .join("")
    : `<span class="muted">${t(emptyKey)}</span>`;
  return `
    <section class="remove-section">
      <h4>${title} <span class="muted">(${cards.length})</span>${note}</h4>
      <div class="remove-cards">${body}</div>
    </section>`;
}

export function removalOverlay(view, store) {
  const state = store.removal;
  if (!state || !state.open) return "";
  const me = view.players[view.you];
  const removable = new Set(view.legal.removable || []);
  const cost = me.removal_cost;
  if (state.peek) {
    return `<div class="remove-peek"><button class="primary" data-action="peek-off">${icon("cards")}${t("ui.remove.back")}</button></div>`;
  }
  let confirm = "";
  if (state.confirm) {
    const inHand = (me.hand || []).find((c) => c.uid === state.confirm);
    const card = inHand || [...me.in_play, ...me.discard].find((c) => c.uid === state.confirm);
    if (card) {
      const key = inHand ? "ui.remove.confirm_hand" : "ui.remove.confirm";
      confirm = `
        <div class="remove-confirm">
          <p>${esc(t(key, { card_name: cardName(card.id), cost }))}</p>
          <div class="prompt-row">
            <button class="danger" data-action="confirm-remove" data-uid="${card.uid}">${icon("trash")}${t("ui.remove.yes")}</button>
            <button data-action="confirm-no">${t("ui.remove.no")}</button>
          </div>
        </div>`;
    }
  }
  const handNote = (me.hand || []).length && !(me.hand || []).some((c) => removable.has(c.uid))
    ? ` <span class="muted">· ${t("ui.remove.keep_two", { min: view.rules.min_hand })}</span>`
    : "";
  return `
    <div class="remove-overlay" data-action="close-remove-backdrop">
      <div class="remove-dialog" data-stop>
        <div class="remove-head">
          <h3>${t("ui.remove.title", { cost })}</h3>
          <div class="prompt-actions">
            <button data-action="peek-on">${icon("cards")}${t("ui.remove.peek")}</button>
            <button data-action="close-remove">${icon("cancel")}${t("ui.remove.cancel")}</button>
          </div>
        </div>
        ${confirm}
        ${section(t("ui.remove.hand"), me.hand || [], removable, "ui.remove.empty", handNote)}
        ${section(t("ui.remove.played"), me.in_play, removable, "ui.remove.empty")}
        ${section(t("ui.remove.discard"), me.discard, removable, "ui.remove.empty")}
      </div>
    </div>`;
}
