// Inline panel to move class resource onto / off a unit that keeps it (143 "put and take any gold on this unit").
import { t } from "../i18n.js";
import { icon } from "../icons.js";
import { cardName, esc, findUnit, resourceName } from "./util.js";

const STEPS = [1, 2, 5];

function amounts(most) {
  const out = STEPS.filter((n) => n < most);
  if (most > 0) out.push(most);
  return out;
}

export function bankPanel(view, store) {
  const uid = store.bankEdit;
  const limits = uid ? (view.legal.bank || {})[uid] : null;
  const found = uid ? findUnit(view, uid) : null;
  if (!limits || !found) return "";
  const resource_name = resourceName(view.players[view.you].resource.key);
  const row = (label, sign, most) =>
    most > 0
      ? `<div class="prompt-row wrap"><span class="label">${label}</span>${amounts(most)
          .map((n) => `<button class="option" data-action="bank" data-uid="${uid}" data-amount="${sign * n}">${n === most && n > 1 ? t("ui.bank.all", { amount: n }) : n}</button>`)
          .join("")}</div>`
      : "";
  return `
    <div class="prompt bank">
      <div class="prompt-head">
        <span class="prompt-title">${icon("coin")} ${esc(t("ui.bank.title", { card_name: cardName(found.unit.id), amount: limits.stored, resource_name }))}</span>
        <span class="prompt-actions"><button data-action="bank-close">${icon("check")}${t("ui.bank.done")}</button></span>
      </div>
      <div class="muted">${t("ui.bank.hint")}</div>
      ${row(t("ui.bank.put", { resource_name }), 1, limits.put)}
      ${row(t("ui.bank.take", { resource_name }), -1, limits.take)}
    </div>`;
}
