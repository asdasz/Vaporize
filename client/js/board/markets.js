// Market columns: the shared market (+ basic supply) on the left, private markets on the right.
// Cards are shown whole and stacked top -> bottom. In the shared market the top card is the "+1" slot
// and the bottom one the "−1" slot: a refresh slides the cards down, the bottom card goes to the
// removed pile below the row and a new card comes out of the deck above it.
import { t } from "../i18n.js";
import { icon } from "../icons.js";
import { marketCard } from "./card.js";
import { esc, seatColor } from "./util.js";

const deckPile = (key, m) => `
  <div class="pile deck" data-pile="${key}-deck" title="${t("ui.market.deck", { count: m.deck_count })}">
    <span class="pile-label">${t("ui.market.deck_pile")}</span><b>${m.deck_count}</b></div>`;

const removedPile = (key, m) => `
  <div class="pile removed" data-pile="${key}-removed" title="${t("ui.market.removed", { count: m.removed_count })}">
    <span class="pile-label">${t("ui.market.removed_pile")}</span><b>${m.removed_count}</b></div>`;

export function sharedMarket(view) {
  const me = view.players[view.you];
  const myTurn = view.current === view.you && view.phase === "actions";
  const m = view.shared_market;
  const legal = view.legal.market || {};
  const buyable = new Set(legal.shared_buy || []);
  const cards = m.row
    .map((entry, slot) =>
      marketCard(entry, {
        affordable: myTurn && entry ? entry.price <= me.inf : null,
        showModifier: true,
        buy: buyable.has(slot) ? { market: "shared", slot } : null,
        altBuy: altFor(legal, "shared", slot),
      }),
    )
    .join("");
  return `
    <div class="box market-col">
      <div class="market-head"><h3>${t("ui.market.shared")}</h3>${refreshButton("shared", legal.shared_refresh)}</div>
      <div class="market-row">${deckPile("shared", m)}${cards}${removedPile("shared", m)}</div>
      ${basicSupply(view, legal)}
    </div>`;
}

// The basic supply: a separate pile you can always buy from, at its printed price.
function basicSupply(view, legal) {
  const b = view.basic_supply;
  if (!b) return "";
  const card = b.card
    ? marketCard(
        { card: b.card, price: b.price, modifier: 0 },
        { affordable: legal.basic_buy ?? null, buy: legal.basic_buy ? { market: "basic", slot: 0 } : null, altBuy: altFor(legal, "basic", 0) },
      )
    : `<div class="mcard empty">${t("ui.market.basic_empty")}</div>`;
  return `
    <div class="basic-supply">
      <h3>${t("ui.market.basic")} <span class="muted">· ${t("ui.market.basic_left", { count: b.count })}</span></h3>
      <div class="basic-stack ${b.count > 1 ? "stacked" : ""}">${card}</div>
    </div>`;
}

// One button per player, side by side, to switch which private market is shown. Yours is buyable.
export function privateMarkets(view, store) {
  const openSeat = store.openMarket === "self" || store.openMarket === null ? view.you : Number(store.openMarket);
  const tabs = view.players
    .map((p) => {
      const label = p.seat === view.you ? t("ui.market.you", { name: p.name }) : esc(p.name);
      const open = openSeat === p.seat ? "open" : "";
      return `<button class="tab ${open}" style="--seat-color:${seatColor(p.seat)}" data-action="market" data-seat="${p.seat}">${label}</button>`;
    })
    .join("");

  const p = view.players[openSeat];
  const mine = p.seat === view.you;
  const myTurn = mine && view.current === view.you && view.phase === "actions";
  const row = p.private_market.row;
  const cards = row.every((c) => c === null)
    ? `<span class="muted">${t("ui.market.no_cards")}</span>`
    : row
        .map((entry, slot) =>
          marketCard(entry, {
            affordable: myTurn && entry ? entry.price <= p.inf : null,
            ownerSeat: p.seat,
            buy: mine && (view.legal.market?.private_buy || []).includes(slot) ? { market: "private", slot } : null,
            altBuy: mine ? altFor(view.legal.market || {}, "private", slot) : null,
          }),
        )
        .join("");
  const note = mine ? refreshButton("private", view.legal.market?.private_refresh) : `<span class="muted">${t("ui.market.view_only")}</span>`;
  const key = `private${p.seat}`;
  return `
    <div class="box market-col">
      <div class="market-head"><h3>${t("ui.market.private")}</h3>${note}</div>
      <div class="tabs">${tabs}</div>
      <div class="market-row">${deckPile(key, p.private_market)}${cards}${removedPile(key, p.private_market)}</div>
    </div>`;
}

// Green refresh button when refreshing is possible right now (cost 0 = the free shared refresh).
function refreshButton(market, cost) {
  if (cost === null || cost === undefined) return "";
  const label = cost === 0 ? t("ui.market.refresh_free") : t("ui.market.refresh", { cost });
  return `<button class="refresh-btn" data-action="refresh" data-market="${market}">${icon("refresh")}${label}</button>`;
}

const altFor = (legal, market, slot) => (legal.alt_buy || []).find((a) => a.market === market && a.slot === slot) || null;
