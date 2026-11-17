// Card renderers: mini unit (tier table), market card, hand card.
import { t } from "../i18n.js";
import { icon } from "../icons.js";
import { cardName, esc, rulesText, seatColor } from "./util.js";

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

// opts.target: valid target of the pending prompt (clickable, red tint); opts.assigned: split damage so far
export function miniUnit(card, { target = false, assigned = 0 } = {}) {
  const classes = ["unit", card.tapped ? "tapped" : "", target ? "target" : ""].join(" ");
  const action = target ? `data-action="target" data-uid="${card.uid}"` : `data-uid="${card.uid}"`;
  const badge = assigned ? `<span class="assigned">−${assigned}</span>` : "";
  return `
    <div class="${classes}" style="border-color:${seatColor(card.owner)}" title="${tooltip(card)}" ${action}>
      ${statusBadges(card.status)}${badge}
      <div class="name">${elementIcons(card.elements)}<span>${esc(cardName(card.id))}</span></div>
      <div class="stats">
        <span title="${t("ui.card.attack")}">${icon("attack")}${card.attack}</span>
        <span title="${t("ui.card.health")}">${icon("health")}${card.hp}</span>
      </div>
    </div>`;
}

export const emptySlot = (label = "") => `<div class="slot">${esc(label)}</div>`;

export function marketCard(entry, { affordable = null, showModifier = false, ownerSeat = null } = {}) {
  if (!entry) return `<div class="mcard empty">${t("ui.market.empty")}</div>`;
  const { card, price, modifier } = entry;
  const priceClass = affordable === true ? "ok" : "";
  const dim = affordable === false ? "dim" : "";
  const border = ownerSeat !== null ? `style="border:2px solid ${seatColor(ownerSeat)}"` : "";
  const mod = showModifier && modifier ? `<span class="mod">${modifier > 0 ? `+${modifier}` : `−${-modifier}`}</span>` : "";
  return `
    <div class="mcard ${dim}" ${border} title="${tooltip(card)}">
      <div class="name">${elementIcons(card.elements)}<span>${esc(cardName(card.id))}</span></div>
      <span class="price ${priceClass}">${price} ${mod}</span>
    </div>`;
}

export function handCard(card, { playable = false, blocked = false, choose = false } = {}) {
  const classes = ["hcard", playable ? "playable" : "", blocked ? "blocked" : "", choose ? "choosable" : ""].join(" ");
  const attrs = choose
    ? `data-action="choose-card" data-uid="${card.uid}"`
    : `draggable="true" data-hand-uid="${card.uid}" data-playable="${playable ? 1 : 0}"`;
  const stats =
    card.type === "unit"
      ? `<div class="stats"><span>${icon("attack")}${card.attack}</span><span>${icon("health")}${card.health}</span></div>`
      : "";
  return `
    <div class="${classes}" ${attrs} title="${tooltip(card)}">
      <div class="top">${elementIcons(card.elements)}<span class="cost">${card.cost}</span></div>
      <div class="name">${esc(cardName(card.id))}</div>
      <div class="type">${t(`ui.card.types.${card.type}`)}</div>
      <div class="text">${rulesText(card.id)}</div>
      ${stats}
      ${card.number ? `<div class="num">No. ${String(card.number).padStart(3, "0")}</div>` : ""}
    </div>`;
}

export const hiddenCard = () => `<div class="hcard hidden"></div>`;
