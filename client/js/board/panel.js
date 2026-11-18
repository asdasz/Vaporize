// Bottom panel for the player we're viewing as: stats, available actions, hand, end turn.
import { t } from "../i18n.js";
import { icon } from "../icons.js";
import { handCard, hiddenCard } from "./card.js";
import { promptPanel } from "./prompt.js";
import { swapPanel } from "./swap.js";
import { cardName, findUnit, playerName, resourceName, seatColor, winnerNames } from "./util.js";

const ELEMENTS = ["fire", "water", "wind", "lightning", "shadow"];

function stats(me) {
  const res = me.resource;
  const els = ELEMENTS.map(
    (e) => `<span class="${me.played_elements[e] ? "has" : ""}" title="${t(`ui.elements.${e}`)}">${icon(e)}${me.played_elements[e]}</span>`,
  ).join("");
  return `
    <div class="stats-row">
      <div class="stat"><div class="label">${t("ui.panel.inf")}</div><div class="big inf">${me.inf}</div></div>
      <div class="stat"><div class="label">${t("ui.panel.resource", { resource_name: resourceName(res.key), limit: res.limit ?? "–" })}</div>
        <div class="big">${res.value}<small> / ${res.limit ?? "–"}</small></div></div>
      <div class="stat"><div class="label">${t("ui.panel.removal")}</div><div class="big">${me.removal_cost ?? "–"}<small> inf</small></div></div>
      <div class="stat"><div class="label">${t("ui.panel.played_elements")}</div><div class="els-count">${els}</div></div>
      <div class="stat" style="margin-left:auto;text-align:right"><div class="label">${t("ui.panel.piles")}</div>
        <div class="big" style="font-size:16px">${me.deck_count} / ${me.discard.length}</div></div>
    </div>`;
}

function chips(view, store) {
  const out = [];
  const myTurn = view.current === view.you && view.phase === "actions";
  if (view.phase === "game_over") {
    out.push(`<span class="banner">${t("ui.panel.game_over", { winner_names: winnerNames(view, view.winners) })}</span>`);
  } else if (!myTurn) {
    out.push(`<span class="chip info">${t("ui.panel.waiting", { player: playerName(view, view.current) })}</span>`);
  } else {
    const left = view.legal.plays_left;
    out.push(
      left > 0
        ? `<span class="chip">${icon("cards")}${t("ui.panel.plays_left", { count: left })}</span>`
        : `<span class="chip done">${t("ui.panel.no_plays_left", { min: view.rules.min_hand })}</span>`,
    );
    if (left > 0) out.push(`<span class="chip info">${icon("arrowUp")}${t("ui.panel.drag_hint")}</span>`);
    const swap = view.legal.element_swap || {};
    if (swap.has) {
      out.push(
        swap.available
          ? `<span class="chip">⇄ ${t("ui.swap.chip")}</span>`
          : `<span class="chip done">⇄ ${t("ui.swap.chip_used")}</span>`,
      );
    }
    const attackers = Object.keys(view.legal.attacks || {}).length;
    if (attackers) out.push(`<span class="chip">${icon("attack")}${t("ui.panel.attacks", { count: attackers })}</span>`);
    if (view.legal.market?.shared_refresh === 0) out.push(`<span class="chip">${icon("refresh")}${t("ui.panel.free_refresh")}</span>`);
    for (const mod of view.players[view.you].turn_modifiers || []) {
      if (mod.kind === "next_spell_invoke_bonus") out.push(`<span class="chip info">${t("ui.panel.next_spell", { amount: mod.amount })}</span>`);
      if (mod.kind === "next_spell_twice") out.push(`<span class="chip info">${t("ui.panel.next_twice")}</span>`);
    }
    if (store.attacker && (view.legal.attacks || {})[store.attacker]) {
      const unit = findUnit(view, store.attacker);
      if (unit) out.push(`<span class="chip info">${icon("attack")}${t("ui.panel.select_target", { card_name: cardName(unit.unit.id) })}</span>`);
    }
    const develops = Object.keys(view.legal.develop || {}).length;
    const removable = (view.legal.removable || []).length;
    if (removable) {
      out.push(`<button class="chip chip-btn" data-action="open-remove">${icon("trash")}${t("ui.panel.remove_chip", { cost: view.players[view.you].removal_cost })}</button>`);
    }
    if (develops) out.push(`<span class="chip">${icon("arrowUp")}${t("ui.panel.develops", { count: develops })}</span>`);
    out.push(`<span class="chip info">${icon("star")}${t("ui.panel.eot_vp", { vp: view.players[view.you].eot_vp })}</span>`);
  }
  if (store.error) {
    const params = { ...store.error.params };
    out.push(`<span class="chip error">${t(store.error.key, params)}</span>`);
  }
  return `<div class="chips">${out.join("")}</div>`;
}

function turnButtons(view, myTurn) {
  const { can_undo: canUndo, undo_card: undoCard, undo_count: undoCount } = view.legal;
  const undoHint = undoCard ? t("ui.panel.undo_hint", { card_name: cardName(undoCard) }) : "";
  const off = (on) => (on ? "" : "disabled");
  return `
    <div class="turn-buttons">
      <button data-action="undo" title="${undoHint}" ${off(myTurn && canUndo)}>${icon("undo")}${t("ui.panel.undo")}</button>
      <button data-action="cancel-turn" title="${t("ui.panel.cancel_hint")}" ${off(myTurn && undoCount > 0)}>${icon("cancel")}${t("ui.panel.cancel_turn")}</button>
      <button class="end-turn ${myTurn ? "go" : ""}" data-action="end-turn" title="${t("ui.panel.end_turn_hint")}" ${off(myTurn)}>${icon("check")}${t("ui.panel.end_turn")}</button>
    </div>`;
}

export function playerPanel(view, store) {
  const me = view.players[view.you];
  const myTurn = view.current === view.you && view.phase === "actions";
  const playable = new Set(view.legal.playable);
  const swapOptions = view.legal.element_swap?.options || {};
  const locked = new Set(me.locked_cards || []);
  const hand = (me.hand || [])
    .map((card) =>
      handCard(card, {
        locked: locked.has(card.uid),
        playable: playable.has(card.uid),
        blocked: myTurn && !playable.has(card.uid),
        canSwap: Boolean(swapOptions[card.uid]),
        swap: store.swap && store.swap.uid === card.uid ? store.swap : null,
      }),
    )
    .join("");
  const filler = me.hand ? "" : Array.from({ length: me.hand_count }, hiddenCard).join("");
  return `
    <div class="panel" style="--seat-color:${seatColor(me.seat)}">
      ${stats(me)}
      ${chips(view, store)}
      ${promptPanel(view, store)}
      ${swapPanel(view, store)}
      ${eotPanel(view, store)}
      <div class="hand-row">
        <div class="hand">${hand}${filler}</div>
        ${turnButtons(view, myTurn)}
      </div>
    </div>`;
}

// Before ending the turn: optional end-of-turn abilities of hand cards (e.g. "discard it for 1 VP").
function eotPanel(view, store) {
  if (!store.eot) return "";
  const me = view.players[view.you];
  const cards = (me.hand || []).filter((c) => c.hand_eot);
  const rows = cards
    .map((c) => {
      const on = store.eot.discards.includes(c.uid);
      return `<label class="eot-row"><input type="checkbox" data-change="eot-discard" data-uid="${c.uid}" ${on ? "checked" : ""}>
        ${t("ui.eot.discard_for_vp", { card_name: cardName(c.id), vp: c.hand_eot.discard_for_vp })}</label>`;
    })
    .join("");
  return `
    <div class="prompt eot">
      <div class="prompt-head"><span class="prompt-title">${t("ui.eot.title")}</span>
        <span class="prompt-actions"><button data-action="eot-cancel">${icon("cancel")}${t("ui.prompt.cancel")}</button>
        <button class="primary" data-action="eot-confirm">${icon("check")}${t("ui.eot.confirm")}</button></span></div>
      ${rows}
    </div>`;
}
