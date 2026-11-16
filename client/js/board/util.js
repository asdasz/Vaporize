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
  return t(event.key, p);
}
