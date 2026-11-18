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

// opts.target: valid target of the pending prompt (clickable, red tint); opts.assigned: split damage so far;
// opts.develop: {cost, to} when the viewer can develop this unit right now (green button)
// opts.canAttack: own unit with legal attacks (green, click to select); opts.selected: chosen attacker (blue);
// opts.attackTarget: enemy the selected attacker can hit (red, click to attack)
export function miniUnit(card, { target = false, assigned = 0, develop = null, canAttack = false, selected = false, attackTarget = false } = {}) {
  const classes = [
    "unit", card.tapped ? "tapped" : "", target || attackTarget ? "target" : "", develop || canAttack ? "can-develop" : "",
    selected ? "selected" : "",
  ].join(" ");
  let action = `data-uid="${card.uid}"`;
  if (target) action = `data-action="target" data-uid="${card.uid}"`;
  else if (attackTarget) action = `data-action="attack-target" data-uid="${card.uid}"`;
  else if (canAttack) action = `data-action="select-attacker" data-uid="${card.uid}"`;
  let badge = assigned ? `<span class="assigned">−${assigned}</span>` : "";
  if (develop && !target) {
    const hint = t("ui.tiers.develop_hint", { tier: develop.to, cost: develop.cost });
    badge += `<button class="dev-btn" data-action="develop" data-uid="${card.uid}" title="${hint}">${icon("arrowUp")}${t("ui.tiers.develop_button", { tier: develop.to, cost: develop.cost })}</button>`;
  }
  return `
    <div class="${classes}" style="border-color:${seatColor(card.owner)}" title="${tooltip(card)}" ${action}>
      ${statusBadges(card.status)}${badge}
      <div class="name">${elementIcons(card.elements)}<span>${esc(cardName(card.id))}</span></div>
      <div class="stats">
        <span title="${t("ui.card.attack")}">${icon("attack")}${statText(card.attack)}</span>
        <span title="${t("ui.card.health")}">${icon("health")}${statText(card.hp)}</span>
      </div>
    </div>`;
}

export const emptySlot = (label = "") => `<div class="slot">${esc(label)}</div>`;

// opts.buy: {market, slot} when the viewer can buy this card now (click to buy);
// opts.altBuy: {market, slot, vp} when it can be bought by losing VP instead
export function marketCard(entry, { affordable = null, showModifier = false, ownerSeat = null, buy = null, altBuy = null } = {}) {
  if (!entry) return `<div class="mcard empty">${t("ui.market.empty")}</div>`;
  const { card, price, modifier } = entry;
  const priceClass = affordable === true ? "ok" : "";
  const dim = affordable === false ? "dim" : "";
  const border = ownerSeat !== null ? `style="border:2px solid ${seatColor(ownerSeat)}"` : "";
  const mod = showModifier && modifier ? `<span class="mod">${modifier > 0 ? `+${modifier}` : `−${-modifier}`}</span>` : "";
  return `
    <div class="mcard ${dim} ${buy ? "buyable" : ""}" data-mcard="${card.uid}" ${border} title="${buy ? t("ui.market.buy_hint", { price }) + " · " : ""}${tooltip(card)}"
      ${buy ? `data-action="buy" data-market="${buy.market}" data-slot="${buy.slot}"` : ""}>
      <div class="name">${elementIcons(card.elements)}<span>${esc(cardName(card.id))}</span></div>
      <div class="mtext">${rulesText(card.id)}</div>
      <span class="price ${priceClass}">${price} ${mod}</span>
      ${altBuy ? `<button class="alt-buy" data-action="buy-vp" data-market="${altBuy.market}" data-slot="${altBuy.slot}" title="${t("ui.market.buy_vp_hint", { vp: altBuy.vp })}">${t("ui.market.buy_vp", { vp: altBuy.vp })}</button>` : ""}
    </div>`;
}

// opts.choose: clickable in a prompt; opts.still: display only (no drag, no click), e.g. in the removal overlay;
// opts.canSwap: show the element-swap button; opts.swap: {from, to} chosen for this card (shown on the card)
export function handCard(card, { playable = false, blocked = false, choose = false, still = false, canSwap = false, swap = null } = {}) {
  if (swap) card = { ...card, elements: card.elements.map((e) => (e === swap.from ? swap.to : e)) };
  const classes = ["hcard", playable ? "playable" : "", blocked ? "blocked" : "", choose ? "choosable" : ""].join(" ");
  let attrs = `draggable="true" data-hand-uid="${card.uid}" data-playable="${playable ? 1 : 0}"`;
  if (choose) attrs = `data-action="choose-card" data-uid="${card.uid}"`;
  else if (still) attrs = "";
  const stats =
    card.type === "unit"
      ? `<div class="stats"><span>${icon("attack")}${statText(card.attack)}</span><span>${icon("health")}${statText(card.health)}</span></div>`
      : "";
  return `
    <div class="${classes}" ${attrs} title="${tooltip(card)}">
      <div class="top">
        <span class="${swap ? "swapped" : ""}">${elementIcons(card.elements)}</span>
        ${canSwap ? `<button class="swap-btn ${swap ? "on" : ""}" data-action="swap-open" data-uid="${card.uid}" draggable="false" title="${t("ui.swap.button")}">⇄</button>` : ""}
        <span class="cost">${card.cost}</span>
      </div>
      <div class="name">${esc(cardName(card.id))}</div>
      <div class="type">${t(`ui.card.types.${card.type}`)}</div>
      <div class="text">${rulesText(card.id)}</div>
      ${stats}
      ${card.number ? `<div class="num">No. ${String(card.number).padStart(3, "0")}</div>` : ""}
    </div>`;
}

export const hiddenCard = () => `<div class="hcard hidden"></div>`;
