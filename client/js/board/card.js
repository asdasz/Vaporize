// Card renderers: mini unit (tier table), market card, hand card.
import { t } from "../i18n.js";
import { icon } from "../icons.js";
import { cardName, esc, rulesText, seatColor } from "./util.js";

// Unit stats can be value expressions before the unit enters play, e.g. {invoke: 1} -> "INV+1".
export function statText(value) {
  if (value && typeof value === "object" && "invoke" in value) {
    return value.invoke ? t("ui.card.invoke_stat", { n: value.invoke }) : t("ui.card.invoke_stat0");
  }
  return String(value ?? 0);
}

export function elementIcons(elements) {
  return `<span class="els">${elements.map((e) => icon(e, t(`ui.elements.${e}`))).join("")}</span>`;
}

function statusBadges(status = {}) {
  const items = Object.entries(status).filter(([, n]) => n > 0);
  if (!items.length) return "";
  return `<div class="statuses">${items.map(([k, n]) => `<span title="${t(`ui.status.${k}`)}">${icon(k)}${n}</span>`).join("")}</div>`;
}

function tooltip(card) {
  return esc(`${cardName(card.id)} · ${t(`ui.card.types.${card.type}`)}`);
}

// Name, type and full rules text as plain text (title attribute).
export function fullTooltip(card) {
  const text = rulesText(card.id).replace(/<[^>]+>/g, "");
  return `${tooltip(card)}${text ? `&#10;${text}` : ""}`;
}

// opts.target: valid target of the pending prompt (clickable, red tint); opts.assigned: split damage so far;
// opts.develop: {cost, to} when the viewer can develop this unit right now (green button)
// opts.canAttack: own unit with legal attacks (green, click to select); opts.selected: chosen attacker (blue);
// opts.attackTarget: enemy the selected attacker can hit (red, click to attack)
// opts.developResource: {cost, to, resource} when it can also be developed paying the class resource (145);
// opts.bank: {put, take, resource} for your units that keep resource (143): shows a button opening the bank panel
export function miniUnit(
  card,
  { target = false, assigned = 0, develop = null, developResource = null, bank = null, canAttack = false, selected = false, attackTarget = false } = {},
) {
  const classes = [
    "unit", card.tapped ? "tapped" : "", target || attackTarget ? "target" : "",
    develop || developResource || canAttack || (bank && (bank.put || bank.take)) ? "can-develop" : "",
    selected ? "selected" : "",
  ].join(" ");
  let action = `data-uid="${card.uid}"`;
  if (target) action = `data-action="target" data-uid="${card.uid}"`;
  else if (attackTarget) action = `data-action="attack-target" data-uid="${card.uid}"`;
  else if (canAttack) action = `data-action="select-attacker" data-uid="${card.uid}"`;
  let badge = assigned ? `<span class="assigned">−${assigned}</span>` : "";
  const devButtons = [];
  if (develop && !target) {
    const hint = t("ui.tiers.develop_hint", { tier: develop.to, cost: develop.cost });
    devButtons.push(`<button class="dev-btn" data-action="develop" data-uid="${card.uid}" title="${hint}">${icon("arrowUp")}${t("ui.tiers.develop_button", { tier: develop.to, cost: develop.cost })}</button>`);
  }
  if (developResource && !target) {
    const params = { tier: developResource.to, cost: developResource.cost, resource_name: t(`ui.resources.${developResource.resource}`) };
    devButtons.push(`<button class="dev-btn gold" data-action="develop-resource" data-uid="${card.uid}" title="${t("ui.tiers.develop_hint_resource", params)}">${icon("arrowUp")}${t("ui.tiers.develop_button_resource", params)}</button>`);
  }
  if (devButtons.length) badge += `<span class="dev-btns">${devButtons.join("")}</span>`;
  if (card.stored || bank) {
    const resource = bank?.resource || "gold";
    const title = t("ui.card.stored", { amount: card.stored || 0, resource_name: t(`ui.resources.${resource}`) });
    badge += bank && !target
      ? `<button class="stored-badge" data-action="bank-open" data-uid="${card.uid}" title="${title}">${icon("coin")}${card.stored || 0}</button>`
      : `<span class="stored-badge" title="${title}">${icon("coin")}${card.stored}</span>`;
  }
  return `
    <div class="${classes}" style="border-color:${seatColor(card.owner)}" title="${fullTooltip(card)}" ${action}>
      ${statusBadges(card.status)}${badge}
      <div class="name">${elementIcons(card.elements)}<span>${esc(cardName(card.id))}</span></div>
      <div class="ability">${rulesText(card.id)}</div>
      <div class="stats">
        <span title="${t("ui.card.attack")}">${icon("attack")}${statText(card.attack)}</span>
        <span title="${t("ui.card.health")}">${icon("health")}${statText(card.hp)}</span>
      </div>
    </div>`;
}

export const emptySlot = (label = "") => `<div class="slot">${esc(label)}</div>`;

// Full market card (name, type, price, whole rules text) for the vertical market columns.
// opts.buy: {market, slot} when the viewer can buy this card now (click to buy);
// opts.altBuy: {market, slot, vp} when it can be bought by losing VP instead
export function marketCard(entry, { affordable = null, showModifier = false, ownerSeat = null, buy = null, altBuy = null, slot = null } = {}) {
  if (!entry) return `<div class="mcard empty">${t("ui.market.empty")}</div>`;
  const { card, price, modifier } = entry;
  const priceClass = affordable === true ? "ok" : "";
  const dim = affordable === false ? "dim" : "";
  const border = ownerSeat !== null ? `style="border-left:3px solid ${seatColor(ownerSeat)}"` : "";
  // Printed cost stays on the badge; the slot modifier is shown next to it, e.g. "5 (−1)".
  // Affordability (green badge) uses the real price.
  const mod = showModifier && modifier ? `<span class="mod">(${modifier > 0 ? `+${modifier}` : `−${-modifier}`})</span>` : "";
  const stats =
    card.type === "unit"
      ? `<span class="mstats">${icon("attack")}${statText(card.attack)} ${icon("health")}${statText(card.health)}</span>`
      : "";
  return `
    <div class="mcard ${dim} ${buy ? "buyable" : ""}" data-mcard="${card.uid}" ${slot !== null ? `data-slot="${slot}"` : ""} ${border} title="${buy ? t("ui.market.buy_hint", { price }) : ""}"
      ${buy ? `data-action="buy" data-market="${buy.market}" data-slot="${buy.slot}"` : ""}>
      <div class="mhead">${elementIcons(card.elements)}<span class="mname">${esc(cardName(card.id))}</span>
        <span class="price ${priceClass}">${card.cost}${mod}</span></div>
      <div class="mtype">${t(`ui.card.types.${card.type}`)}${stats}</div>
      <div class="mtext">${rulesText(card.id)}</div>
      ${altBuy ? `<button class="alt-buy" data-action="buy-vp" data-market="${altBuy.market}" data-slot="${altBuy.slot}" title="${t("ui.market.buy_vp_hint", { vp: altBuy.vp })}">${t("ui.market.buy_vp", { vp: altBuy.vp })}</button>` : ""}
    </div>`;
}

// A card played this turn, laid out left to right next to its owner's deck: the whole card (name, type,
// rules text, stats). "md": your own row; "sm": the other players' rows (a little smaller). Hover for full text.
export function playedCard(card, size = "md") {
  const stats =
    card.type === "unit"
      ? `<span class="pstats"><span>${icon("attack")}${statText(card.attack)}</span><span>${icon("health")}${statText(card.health)}</span></span>`
      : "";
  return `
    <div class="pcard ${size}" data-played="${card.uid}" title="${fullTooltip(card)}">
      <span class="phead">${elementIcons(card.elements)}<span class="pcost">${card.cost}</span></span>
      <span class="pname">${esc(cardName(card.id))}</span>
      <span class="ptype">${t(`ui.card.types.${card.type}`)}</span>
      <span class="ptext">${rulesText(card.id)}</span>
      ${stats}
    </div>`;
}

// opts.choose: clickable in a prompt; opts.still: display only (no drag, no click), e.g. in the removal overlay;
// opts.canSwap: show the element-swap button; opts.swap: {from, to} chosen for this card (shown on the card)
export function handCard(card, { playable = false, blocked = false, choose = false, still = false, canSwap = false, swap = null, locked = false } = {}) {
  if (swap) card = { ...card, elements: card.elements.map((e) => (e === swap.from ? swap.to : e)) };
  const classes = ["hcard", playable ? "playable" : "", blocked ? "blocked" : "", choose ? "choosable" : "", locked ? "locked" : ""].join(" ");
  let attrs = `draggable="true" data-hand-uid="${card.uid}" data-playable="${playable ? 1 : 0}"`;
  if (choose) attrs = `data-action="choose-card" data-uid="${card.uid}"`;
  else if (still) attrs = "";
  const stats =
    card.type === "unit"
      ? `<div class="stats"><span>${icon("attack")}${statText(card.attack)}</span><span>${icon("health")}${statText(card.health)}</span></div>`
      : "";
  return `
    <div class="${classes}" ${attrs} data-card="${card.uid}" title="${tooltip(card)}">
      <div class="top">
        <span class="${swap ? "swapped" : ""}">${elementIcons(card.elements)}</span>
        ${canSwap ? `<button class="swap-btn ${swap ? "on" : ""}" data-action="swap-open" data-uid="${card.uid}" draggable="false" title="${t("ui.swap.button")}">⇄</button>` : ""}
        <span class="cost">${card.cost}</span>
      </div>
      <div class="name">${esc(cardName(card.id))}</div>
      <div class="type">${t(`ui.card.types.${card.type}`)}</div>
      <div class="text">${locked ? `<span class="locked-note">${t("ui.card.locked")}</span>` : ""}${rulesText(card.id)}</div>
      ${stats}
      ${card.number ? `<div class="num">No. ${String(card.number).padStart(3, "0")}</div>` : ""}
    </div>`;
}

export const hiddenCard = () => `<div class="hcard hidden"></div>`;
