// Inline panel for the pending choice (invoke amount, target, scouted card, split damage).
import { t } from "../i18n.js";
import { icon } from "../icons.js";
import { handCard } from "./card.js";
import { cardName, esc, findUnit, playerName, resourceName, seatColor } from "./util.js";

function unitButton(view, uid, extra = "", action = "target") {
  const found = findUnit(view, uid);
  if (!found) return "";
  const { unit, tier } = found;
  return `<button class="unit-pick" style="border-color:${seatColor(unit.owner)}" data-action="${action}" data-uid="${uid}">
      ${esc(cardName(unit.id))} · T${tier} · ${esc(playerName(view, unit.owner))} · ${icon("health")}${unit.hp}${extra}</button>`;
}

// Label next to the slider: invoke ("Spend 3 gold → value 3"), free invoke (134) or "pay N times" (142).
export function numberLabel(prompt, value) {
  const resource_name = resourceName(prompt.params.resource);
  if (prompt.key === "prompt.pay_resource_times") {
    return t("ui.prompt.pay_times", { times: value, total: value * prompt.params.cost, resource_name });
  }
  const total = value + (prompt.params.bonus || 0);
  if (prompt.params.free) return t("ui.prompt.value_free", { value: total, resource_name });
  return t("ui.prompt.spend", { spent: value, resource_name, value: total });
}

function numberBody(prompt, draft) {
  const value = draft.value ?? prompt.max;
  const bonus = prompt.params.bonus ? ` ${t("ui.prompt.bonus", { bonus: prompt.params.bonus })}` : "";
  return `
    <div class="prompt-row">
      <input type="range" min="${prompt.min}" max="${prompt.max}" step="1" value="${value}" data-input="number">
      <span class="prompt-value" data-number-label>${esc(numberLabel(prompt, value))}</span>
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

function chooseCardsBody(view, prompt, draft) {
  const picked = new Set(draft.cards || []);
  const tiles = prompt.options
    .map((card) =>
      card.unit // a unit on the board (e.g. "stun N units", "swap 2 units")
        ? `<span class="pick-unit ${picked.has(card.uid) ? "picked" : ""}">${unitButton(view, card.uid, "", "toggle-card")}</span>`
        : `<div class="pick-tile ${picked.has(card.uid) ? "picked" : ""}" data-action="toggle-card" data-uid="${card.uid}">${handCard(card, { still: true })}</div>`,
    )
    .join("");
  const ok = picked.size >= prompt.min && picked.size <= prompt.max;
  return `
    <div class="prompt-row wrap">${tiles}</div>
    <div class="prompt-row"><span class="label">${t("ui.prompt.selected", { count: picked.size })}</span>
      <button class="primary" data-action="confirm-cards" ${ok ? "" : "disabled"}>${icon("check")}${t("ui.prompt.confirm")}</button></div>`;
}

function orderCardsBody(prompt, draft) {
  const order = draft.cards || [];
  const tiles = prompt.options
    .map((card) => {
      const pos = order.indexOf(card.uid);
      return `<div class="pick-tile ${pos >= 0 ? "picked ordered" : ""}" data-action="toggle-card" data-uid="${card.uid}">
          ${pos >= 0 ? `<span class="order-badge">${pos + 1}</span>` : ""}${handCard(card, { still: true })}</div>`;
    })
    .join("");
  const ok = order.length === prompt.options.length;
  return `
    <div class="muted">${t("ui.prompt.order_hint")}</div>
    <div class="prompt-row wrap">${tiles}</div>
    <div class="prompt-row"><button data-action="reset-cards">${t("ui.prompt.reset_order")}</button>
      <button class="primary" data-action="confirm-cards" ${ok ? "" : "disabled"}>${icon("check")}${t("ui.prompt.confirm")}</button></div>`;
}

// Option texts: card options (cards.<id>.options or cards.<id>.<label>), or a UI list (params.labels).
function optionText(prompt, i) {
  const { card, label, labels } = prompt.params;
  if (labels) return t(`${labels}.${i}`);
  return t(`cards.${card}.${label || "options"}.${i}`);
}

function chooseOptionBody(prompt) {
  return `<div class="prompt-row wrap">${prompt.options
    .map((i) => `<button class="option" data-action="choose-option" data-value="${i}">${esc(optionText(prompt, i))}</button>`)
    .join("")}</div>`;
}

function chooseTierBody(prompt) {
  return `<div class="prompt-row wrap">${prompt.options
    .map((tier) => `<button class="option" data-action="choose-option" data-value="${tier}">${t("ui.prompt.tier", { tier })}</button>`)
    .join("")}</div>`;
}

function promptText(view, prompt) {
  const params = { ...prompt.params };
  if (params.resource) params.resource_name = resourceName(params.resource);
  if (params.card) params.card_name = cardName(params.card);
  if (params.position) params.position = t(`ui.positions.${params.position}`);
  if ("player_seat" in params) params.player_name = view.players[params.player_seat]?.name ?? "";
  if (params.element) params.element_name = t(`ui.elements.${params.element}`).toLowerCase();
  if (params.market) params.market_name = t(`ui.market.${params.market}_name`);
  return t(prompt.key === "prompt.invoke" && params.free ? "prompt.invoke_free" : prompt.key, params);
}

export function promptPanel(view, store) {
  const pending = view.pending;
  if (!pending) return "";
  const cardLabel = pending.kind === "end_turn" ? t("ui.pending.end_turn") : pending.card ? cardName(pending.card.id) : "";
  const headKey = pending.kind === "attack" ? "ui.prompt.attacking" : "ui.prompt.playing";
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
  else if (prompt.kind === "choose_cards") body = chooseCardsBody(view, prompt, draft);
  else if (prompt.kind === "order_cards") body = orderCardsBody(prompt, draft);
  else if (prompt.kind === "choose_option") body = chooseOptionBody(prompt);
  else if (prompt.kind === "choose_tier") body = chooseTierBody(prompt);
  const skipLabel = t(prompt.params.skip_key || "ui.prompt.skip");
  const skip = prompt.allow_skip ? `<button class="skip" data-action="skip-choice">${skipLabel}</button>` : "";
  const cancel = prompt.cancellable ? `<button data-action="cancel-choice">${icon("cancel")}${t("ui.prompt.cancel")}</button>` : "";
  return `
    <div class="prompt">
      <div class="prompt-head">
        <span class="label">${t(headKey, { card_name: esc(cardLabel) })}</span>
        <span class="prompt-actions">${skip}${cancel}</span>
      </div>
      <div class="prompt-title">${esc(promptText(view, prompt))}</div>
      ${body}
    </div>`;
}
