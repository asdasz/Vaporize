// Inline panel to pick the Mage element swap for one hand card before playing it.
import { t } from "../i18n.js";
import { icon } from "../icons.js";
import { cardName, esc } from "./util.js";

export function swapPanel(view, store) {
  const uid = store.swapEdit;
  const options = view.legal.element_swap?.options || {};
  if (!uid || !options[uid]) return "";
  const card = (view.players[view.you].hand || []).find((c) => c.uid === uid);
  if (!card) return "";
  const chosen = store.swap && store.swap.uid === uid ? store.swap : null;
  const rows = Object.entries(options[uid])
    .map(([from, targets]) => {
      const buttons = targets
        .map((to) => {
          const on = chosen && chosen.from === from && chosen.to === to;
          return `<button class="el-pick ${on ? "on" : ""}" data-action="swap-pick" data-from="${from}" data-to="${to}" title="${t(`ui.elements.${to}`)}">${icon(to)}${t(`ui.elements.${to}`)}</button>`;
        })
        .join("");
      return `<div class="prompt-row wrap"><span class="label">${t("ui.swap.pick_from")}</span>
        <span class="el-from">${icon(from)}${t(`ui.elements.${from}`)}</span>
        <span class="label">${t("ui.swap.pick_to")}</span>${buttons}</div>`;
    })
    .join("");
  return `
    <div class="prompt swap">
      <div class="prompt-head">
        <span class="prompt-title">${esc(t("ui.swap.title", { card_name: cardName(card.id) }))}</span>
        <span class="prompt-actions">
          <button data-action="swap-clear">${t("ui.swap.clear")}</button>
          <button class="primary" data-action="swap-close">${icon("check")}${t("ui.swap.done")}</button>
        </span>
      </div>
      <div class="muted">${t("ui.swap.hint")}</div>
      ${rows}
    </div>`;
}
