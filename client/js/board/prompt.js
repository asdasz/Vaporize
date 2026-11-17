// Inline panel for the pending choice (invoke amount, target, scouted card, split damage).
import { t } from "../i18n.js";
import { icon } from "../icons.js";
import { handCard } from "./card.js";
import { cardName, esc, findUnit, playerName, resourceName, seatColor } from "./util.js";

function unitButton(view, uid, extra = "") {
  const found = findUnit(view, uid);
  if (!found) return "";
  const { unit, tier } = found;
  return `<button class="unit-pick" style="border-color:${seatColor(unit.owner)}" data-action="target" data-uid="${uid}">
      ${esc(cardName(unit.id))} · T${tier} · ${esc(playerName(view, unit.owner))} · ${icon("health")}${unit.hp}${extra}</button>`;
}

function numberBody(prompt, draft) {
  const value = draft.value ?? prompt.max;
  const res = resourceName(prompt.params.resource);
  const bonus = prompt.params.bonus ? ` ${t("ui.prompt.bonus", { bonus: prompt.params.bonus })}` : "";
  return `
    <div class="prompt-row">
      <input type="range" min="${prompt.min}" max="${prompt.max}" step="1" value="${value}" data-input="number">
      <span class="prompt-value" data-number-label>${t("ui.prompt.spend", { spent: value, resource_name: res, value: value + (prompt.params.bonus || 0) })}</span>
      <span class="muted">${bonus}</span>
    </div>
    <div class="prompt-row"><button class="primary" data-action="confirm-number">${icon("check")}${t("ui.prompt.confirm")}</button></div>`;
}

function chooseUnitBody(view, prompt) {
  return `
    <div class="muted">${t("ui.prompt.click_unit")}</div>
    <div class="prompt-row wrap">${prompt.options.map((uid) => unitButton(view, uid)).join("")}</div>`;
}

function splitBody(view, prompt, draft) {
  const split = draft.split || {};
  const assigned = Object.values(split).reduce((a, b) => a + b, 0);
  const rows = prompt.options
    .map((uid) => {
      const n = split[uid] || 0;
      return `<div class="split-row">
          <button data-action="split" data-uid="${uid}" data-delta="-1" ${n ? "" : "disabled"}>−</button>
          <b>${n}</b>
          <button data-action="split" data-uid="${uid}" data-delta="1" ${assigned < prompt.total ? "" : "disabled"}>+</button>
          ${unitButton(view, uid)}
        </div>`;
    })
    .join("");
  const ready = assigned === prompt.total;
  return `
    <div class="prompt-row"><b>${t("ui.prompt.assigned", { assigned, total: prompt.total })}</b>
      ${prompt.same_tier ? `<span class="chip info">${t("ui.prompt.same_tier")}</span>` : ""}</div>
    <div class="split-list">${rows}</div>
    <div class="prompt-row"><button class="primary" data-action="confirm-split" ${ready ? "" : "disabled"}>${icon("check")}${t("ui.prompt.confirm")}</button></div>`;
}

function chooseCardBody(prompt) {
  return `<div class="prompt-row wrap">${prompt.options.map((card) => handCard(card, { choose: true })).join("")}</div>`;
}

function promptText(prompt) {
  const params = { ...prompt.params };
  if (params.resource) params.resource_name = resourceName(params.resource);
  return t(prompt.key, params);
}

export function promptPanel(view, store) {
  const pending = view.pending;
  if (!pending) return "";
  const cardLabel = pending.card ? cardName(pending.card.id) : "";
  if (!pending.prompt) {
    return `<div class="prompt waiting">${t("ui.prompt.waiting", { player: playerName(view, pending.seat), card_name: cardLabel })}</div>`;
  }
  const prompt = pending.prompt;
  const draft = store.draft || {};
  let body = "";
  if (prompt.kind === "number") body = numberBody(prompt, draft);
  else if (prompt.kind === "choose_unit") body = chooseUnitBody(view, prompt);
  else if (prompt.kind === "split_damage") body = splitBody(view, prompt, draft);
  else if (prompt.kind === "choose_card") body = chooseCardBody(prompt);
  const skipLabel = t(prompt.params.skip_key || "ui.prompt.skip");
  const skip = prompt.allow_skip ? `<button class="skip" data-action="skip-choice">${skipLabel}</button>` : "";
  const cancel = prompt.cancellable ? `<button data-action="cancel-choice">${icon("cancel")}${t("ui.prompt.cancel")}</button>` : "";
  return `
    <div class="prompt">
      <div class="prompt-head">
        <span class="label">${t("ui.prompt.playing", { card_name: esc(cardLabel) })}</span>
        <span class="prompt-actions">${skip}${cancel}</span>
      </div>
      <div class="prompt-title">${esc(promptText(prompt))}</div>
      ${body}
    </div>`;
}
