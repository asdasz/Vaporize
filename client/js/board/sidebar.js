import { t } from "../i18n.js";
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

function cardList(cards) {
  if (!cards.length) return `<span class="muted">${t("ui.side.nothing")}</span>`;
  return `<ul class="list">${grouped(cards)
    .map(({ card, count }) => `<li>${elementIcons(card.elements)} ${esc(cardName(card.id))}<span class="count">×${count}</span></li>`)
    .join("")}</ul>`;
}

export function sidebar(view) {
  const me = view.players[view.you];
  const log = [...view.log].reverse().map((e) => `<li>${esc(eventText(view, e))}</li>`).join("");
  return `
    <div class="box"><h3>${t("ui.side.in_play")}</h3>${cardList(me.in_play)}</div>
    <div class="box"><h3>${t("ui.side.discard", { count: me.discard.length })}</h3>${cardList(me.discard)}</div>
    <div class="box"><h3>${t("ui.side.removed", { count: me.removed.length })}</h3>${cardList(me.removed)}</div>
    <div class="box"><h3>${t("ui.side.log")}</h3><ul class="list log">${log}</ul></div>`;
}
