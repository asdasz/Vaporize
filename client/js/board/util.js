import { raw, t } from "../i18n.js";

export function esc(value) {
  return String(value).replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);
}

export const seatColor = (seat) => `var(--seat-${seat})`;

export const cardName = (id) => t(`cards.${id}.name`);

export const playerName = (view, seat) => view.players[seat]?.name ?? `#${seat}`;

export const resourceName = (key) => t(`ui.resources.${key}`);

// Card rules text: escape, then **bold** for keywords / labels.
export function rulesText(id) {
  const text = raw(`cards.${id}.text`);
  if (typeof text !== "string") return "";
  return esc(text).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
}

export function winnerNames(view, seats) {
  return seats.map((s) => playerName(view, s)).join(", ");
}

// Turn engine event params into display params (names instead of ids).
export function eventText(view, event) {
  const p = { ...event.params };
  if ("seat" in p) p.player = playerName(view, p.seat);
  if ("first_player" in p) p.player = playerName(view, p.first_player);
  if ("card" in p) p.card_name = cardName(p.card);
  if ("resource" in p) p.resource_name = resourceName(p.resource);
  if ("winners" in p) p.winner_names = winnerNames(view, p.winners);
  if ("owner" in p) p.owner_name = playerName(view, p.owner);
  if ("attacker" in p) p.attacker_name = cardName(p.attacker);
  if ("target" in p) p.card_name = cardName(p.target);
  if ("market" in p) p.market_name = t(`ui.market.${p.market}_name`);
  if ("status" in p) p.status_name = t(`ui.status.${p.status}`).toLowerCase();
  if ("position" in p) p.position = t(`ui.positions.${p.position}`);
  if ("a" in p) p.a_name = cardName(p.a);
  if ("b" in p) p.b_name = cardName(p.b);
  if ("from" in p) p.from_name = t(`ui.elements.${p.from}`);
  if ("to" in p) p.to_name = t(`ui.elements.${p.to}`);
  if ("keyword" in p) p.keyword_name = t(`keywords.${p.keyword}.name`);
  return t(event.key, p);
}

// All units on the board (own tiers, tokens, shared tier 4) as {unit, tier}.
export function boardUnits(view) {
  const out = [];
  for (const p of view.players) {
    for (const [tier, row] of Object.entries(p.tiers)) row.forEach((u) => u && out.push({ unit: u, tier: Number(tier) }));
    p.tokens.forEach((u) => out.push({ unit: u, tier: 1 }));
  }
  view.tier4.forEach((u) => u && out.push({ unit: u, tier: 4 }));
  return out;
}

export const findUnit = (view, uid) => boardUnits(view).find((x) => x.unit.uid === uid);

// The pending prompt if *we* are the one choosing, else null.
export const myPrompt = (view) => (view.pending && view.pending.prompt ? view.pending.prompt : null);
