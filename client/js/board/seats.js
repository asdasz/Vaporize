// Seats around the table: each player's plate (outside the table) and their card row:
// deck (face down) on the left, cards played this turn left -> right, discard pile (face up) on the right.
import { raw, t } from "../i18n.js";
import { icon } from "../icons.js";
import { elementIcons, fullTooltip, playedCard } from "./card.js";
import { relativeSeat } from "./table.js";
import { esc, seatColor } from "./util.js";

// Hover text for a class name: passives, prepare and invoke (plain text).
export function classTooltip(classId) {
  const plain = (s) => String(s || "").replace(/\*\*/g, "");
  const passives = raw(`classes.${classId}.passives`) || [];
  const lines = [
    t(`classes.${classId}.name`),
    ...passives.map((p) => `• ${plain(p)}`),
    `${t("ui.seat.prepare")}: ${plain(raw(`classes.${classId}.prepare`))}`,
    `${t("ui.seat.invoke")}: ${plain(raw(`classes.${classId}.invoke`))}`,
  ];
  return esc(lines.join("\n")).replace(/\n/g, "&#10;");
}

// Where each relative seat sits: you at the bottom, the others clockwise (left, top, right).
const SIDES = { 1: ["bottom"], 2: ["bottom", "top"], 3: ["bottom", "top", "top"], 4: ["bottom", "left", "top", "right"] };

export function seatSide(view, seat) {
  return SIDES[view.players.length][relativeSeat(view, seat)];
}

const backs = (count) => `<span class="backs">${"<i></i>".repeat(Math.min(count, 12))}</span>`;

export function deckPile(p) {
  return `<div class="spile deck" data-pile="seat${p.seat}-deck" title="${t("ui.seat.deck", { count: p.deck_count })}">
      <span class="pile-label">${t("ui.market.deck_pile")}</span><b>${p.deck_count}</b></div>`;
}

// Face up: the top card's elements and number, the count, click to see the whole pile.
export function discardPile(p) {
  const top = p.discard[p.discard.length - 1];
  const face = top ? `${elementIcons(top.elements)}<span class="pile-num">${String(top.number ?? "").padStart(3, "0")}</span>` : "";
  return `<button class="spile discard ${top ? "" : "empty"}" data-pile="seat${p.seat}-discard" data-action="view-pile" data-seat="${p.seat}" data-which="discard"
      title="${top ? fullTooltip(top) : t("ui.seat.discard", { count: 0 })}">
      ${face}<span class="pile-label">${t("ui.seat.discard_pile")}</span><b>${p.discard.length}</b></button>`;
}

export function playedRow(p, size) {
  const cards = p.in_play.map((c) => playedCard(c, size)).join("");
  return `<div class="played ${size}" data-played-row="${p.seat}">${cards || `<span class="muted played-empty">${t("ui.seat.played_empty")}</span>`}</div>`;
}

function plate(view, p) {
  const current = p.seat === view.current && view.phase !== "game_over";
  const res = p.resource;
  const removed = p.removed_count
    ? `<button class="mini-link" data-action="view-pile" data-seat="${p.seat}" data-which="removed">${icon("trash")}${p.removed_count}</button>`
    : "";
  return `
    <div class="plate ${current ? "current" : ""}" style="--seat-color:${seatColor(p.seat)}">
      <div class="plate-head"><span class="dot" style="background:${seatColor(p.seat)}"></span>
        <b>${esc(p.name)}</b><span class="muted class-name" title="${classTooltip(p.class_id)}">${t(`classes.${p.class_id}.name`)}</span>
        ${current ? `<span class="turn-badge">${t("ui.seat.turn")}</span>` : ""}</div>
      <div class="plate-stats">
        <span class="vp" title="VP">${icon("star")}${p.vp}</span>
        <span class="eot ${p.eot_vp ? "has" : ""}">${t("ui.tiers.eot_vp", { vp: p.eot_vp })}</span>
        <span title="${t("ui.seat.hand", { count: p.hand_count })}">${backs(p.hand_count)} ${p.hand_count}</span>
        ${current ? `<span>${t("ui.seat.inf", { inf: p.inf })}</span>` : ""}
        <span class="muted">${res.value}/${res.limit ?? "–"} ${t(`ui.resources.${res.key}`)}</span>
        ${p.tax ? `<span class="muted">${t("ui.seat.tax", { amount: p.tax })}</span>` : ""}
        ${removed}
      </div>
    </div>`;
}

// One opponent: plate + card row. Side seats (4 players) are laid out vertically.
export function opponentSeat(view, p) {
  const side = seatSide(view, p.seat);
  const vertical = side === "left" || side === "right";
  return `
    <div class="seat ${vertical ? "vertical" : ""}" style="--seat-color:${seatColor(p.seat)}">
      ${plate(view, p)}
      <div class="seat-cards">${deckPile(p)}${playedRow(p, "sm")}${discardPile(p)}</div>
    </div>`;
}

export function seatsOn(view, side) {
  return view.players
    .filter((p) => p.seat !== view.you && seatSide(view, p.seat) === side)
    .map((p) => opponentSeat(view, p))
    .join("");
}

// The viewer's own card row at the top of the bottom panel.
export function mySeatCards(view) {
  const me = view.players[view.you];
  return `<div class="seat-cards mine">${deckPile(me)}${playedRow(me, "md")}${discardPile(me)}</div>`;
}

export { plate };
