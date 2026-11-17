import { t } from "../i18n.js";
import { icon } from "../icons.js";
import { elementIcons } from "./card.js";
import { cardName, esc, eventText } from "./util.js";

function grouped(cards) {
  const map = new Map();
  for (const c of cards) {
    const entry = map.get(c.id) || { card: c, count: 0, uids: [] };
    entry.count += 1;
    entry.uids.push(c.uid);
    map.set(c.id, entry);
  }
  return [...map.values()];
}

// removal: {cost, removable: Set(uid)} to show a green "Remove" button on cards that can be removed now
function cardList(cards, removal = null) {
  if (!cards.length) return `<span class="muted">${t("ui.side.nothing")}</span>`;
  return `<ul class="list">${grouped(cards)
    .map(({ card, count, uids }) => {
      const uid = removal && uids.find((u) => removal.removable.has(u));
      const button = uid
        ? `<button class="remove-btn" data-action="remove-card" data-uid="${uid}" title="${t("ui.side.remove_hint", { cost: removal.cost })}">${icon("trash")}${t("ui.side.remove", { cost: removal.cost })}</button>`
        : "";
      return `<li>${elementIcons(card.elements)} ${esc(cardName(card.id))}<span class="count">×${count}</span>${button}</li>`;
    })
    .join("")}</ul>`;
}

export function sidebar(view) {
  const me = view.players[view.you];
  const removal = { cost: me.removal_cost, removable: new Set(view.legal.removable || []) };
  const log = [...view.log].reverse().map((e) => `<li>${esc(eventText(view, e))}</li>`).join("");
  return `
    <div class="box"><h3>${t("ui.side.in_play")}</h3>${cardList(me.in_play, removal)}</div>
    <div class="box"><h3>${t("ui.side.discard", { count: me.discard.length })}</h3>${cardList(me.discard, removal)}</div>
    <div class="box"><h3>${t("ui.side.removed", { count: me.removed.length })}</h3>${cardList(me.removed)}</div>
    <div class="box"><h3>${t("ui.side.log")}</h3><ul class="list log">${log}</ul></div>`;
}
