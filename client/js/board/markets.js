import { t } from "../i18n.js";
import { icon } from "../icons.js";
import { marketCard } from "./card.js";
import { esc, seatColor } from "./util.js";

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
      }),
    )
    .join("");
  return `
    <div class="box">
      <div class="market-head">
        <h3>${t("ui.market.shared")} <span class="muted">· ${t("ui.market.deck", { count: m.deck_count })} · ${t("ui.market.removed", { count: m.removed_count })}</span></h3>
        ${refreshButton("shared", legal.shared_refresh)}
      </div>
      <div class="market-row">${cards}</div>
    </div>`;
}

export function privateMarkets(view, store) {
  const openSeat = store.openMarket === "self" ? view.you : store.openMarket;
  const tabs = view.players
    .map((p) => {
      const label = p.seat === view.you ? t("ui.market.you", { name: p.name }) : esc(p.name);
      const open = String(openSeat) === String(p.seat) ? "open" : "";
      return `<button class="tab ${open}" style="border-color:${seatColor(p.seat)}" data-action="market" data-seat="${p.seat}">${label}</button>`;
    })
    .join("");

  let body = `<span class="muted">${t("ui.market.click_to_show")}</span>`;
  if (openSeat !== null && openSeat !== undefined) {
    const p = view.players[Number(openSeat)];
    const mine = p.seat === view.you;
    const myTurn = mine && view.current === view.you && view.phase === "actions";
    const row = p.private_market.row;
    const cards = row.every((c) => c === null)
      ? `<span class="muted" style="align-self:center">${t("ui.market.no_cards")}</span>`
      : row
          .map((entry, slot) =>
            marketCard(entry, {
              affordable: myTurn && entry ? entry.price <= p.inf : null,
              ownerSeat: p.seat,
              buy: mine && (view.legal.market?.private_buy || []).includes(slot) ? { market: "private", slot } : null,
            }),
          )
          .join("");
    const note = mine
      ? refreshButton("private", view.legal.market?.private_refresh)
      : `<span class="muted" style="align-self:center">${t("ui.market.view_only")}</span>`;
    body = `${cards}${note}`;
  }

  return `
    <div class="box">
      <div class="market-head">
        <div class="tabs"><h3 style="margin:0 6px 0 0">${t("ui.market.private")}</h3>${tabs}</div>
        <span class="muted">${icon("cards")}</span>
      </div>
      <div class="market-row">${body}</div>
    </div>`;
}

// Green refresh button when refreshing is possible right now (cost 0 = the free shared refresh).
function refreshButton(market, cost) {
  if (cost === null || cost === undefined) return "";
  const label = cost === 0 ? t("ui.market.refresh_free") : t("ui.market.refresh", { cost });
  return `<button class="refresh-btn" data-action="refresh" data-market="${market}">${icon("refresh")}${label}</button>`;
}
