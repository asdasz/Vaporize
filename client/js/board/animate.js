// Board animations. Every render compares the board before and after (snapshotBoard → animateBoard):
// - another player's card or unit: zooms to the middle of the screen, then flies to its place (spotlight)
// - your own card: slides from the hand into the played row; a unit slides from the hand onto the table
// - units: pop in when they enter, slide + glow on tier up, shake with "−N" when damaged, "+N" when healed,
//   fly to the owner's discard pile when destroyed
// - hand: drawn cards come out of your deck pile (one after the other)
// - markets: a bought card is shown in the middle of the screen, then flies to the buyer's discard pile
//   (shorter for your own buys); the new card appears in the same slot;
//   on refresh the cards slide down, the bottom one flies to the removed pile, the new one comes from the deck
// - end of turn: played cards fly to the discard pile
import { handCard } from "./card.js";
import { boardUnits } from "./util.js";

const DURATION = 420;
const EASE = "cubic-bezier(.2,.7,.2,1)";

const reducedMotion = () => window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const center = (r) => ({ x: r.left + r.width / 2, y: r.top + r.height / 2 });

// Call before the board is re-rendered.
export function snapshotBoard(root) {
  if (!root.querySelectorAll) return null;
  const rect = (el) => el.getBoundingClientRect();
  const cards = new Map();
  root.querySelectorAll("[data-mcard]").forEach((el) => {
    cards.set(el.dataset.mcard, { rect: rect(el), html: el.outerHTML, row: rowKey(el), slot: el.dataset.slot });
  });
  const piles = new Map();
  root.querySelectorAll("[data-pile]").forEach((el) =>
    piles.set(el.dataset.pile, { rect: rect(el), count: Number(el.querySelector("b")?.textContent || 0) }),
  );
  const played = new Map();
  root.querySelectorAll("[data-played]").forEach((el) =>
    played.set(el.dataset.played, { rect: rect(el), html: el.outerHTML, seat: el.closest("[data-played-row]")?.dataset.playedRow }),
  );
  const hand = new Map();
  root.querySelectorAll("[data-hand-uid]").forEach((el) => hand.set(el.dataset.handUid, rect(el)));
  const units = new Map();
  root.querySelectorAll(".place[data-uid]").forEach((el) => {
    const unit = el.querySelector(".unit");
    if (unit) units.set(el.dataset.uid, { rect: rect(unit), html: unit.outerHTML, hp: Number(el.dataset.hp), tier: el.dataset.tier, owner: el.dataset.owner });
  });
  return { cards, piles, played, hand, units };
}

function rowKey(el) {
  const pile = el.closest(".market-row")?.querySelector("[data-pile$='-deck']");
  return pile ? pile.dataset.pile.replace(/-deck$/, "") : null;
}

// Animate `el` from where `from` was to where it is now (FLIP), optionally scaled from `scale`.
function flyFrom(el, from, { scale = 1, delay = 0, factor = 1, duration = DURATION } = {}) {
  const to = el.getBoundingClientRect();
  const a = center(from);
  const b = center(to);
  const dx = (a.x - b.x) / factor;
  const dy = (a.y - b.y) / factor;
  if (Math.abs(dx) < 1 && Math.abs(dy) < 1 && scale === 1) return;
  el.animate(
    [{ transform: `translate(${dx}px, ${dy}px) scale(${scale})`, opacity: 0.6 }, { transform: "none", opacity: 1 }],
    { duration, delay, easing: EASE, fill: "backwards" },
  );
}

function popIn(el, delay = 0) {
  el.animate(
    [{ transform: "scale(0.3)", opacity: 0 }, { transform: "scale(1.08)", opacity: 1, offset: 0.7 }, { transform: "none", opacity: 1 }],
    { duration: 450, delay, easing: EASE, fill: "backwards" },
  );
}

// A copy of an element that flies from `from` to `to` and disappears (the original is already gone).
function ghost(html, from, to, { delay = 0, tint = null } = {}) {
  const holder = document.createElement("div");
  holder.innerHTML = html;
  const el = holder.firstElementChild;
  if (!el) return;
  Object.assign(el.style, {
    position: "fixed", left: `${from.left}px`, top: `${from.top}px`, width: `${from.width}px`, height: `${from.height}px`,
    margin: "0", zIndex: "70", pointerEvents: "none", transform: "none",
  });
  if (tint) el.style.background = tint;
  document.body.appendChild(el);
  const a = center(from);
  const b = to ? center(to) : a;
  const anim = el.animate(
    [
      { transform: "none", opacity: 1 },
      { transform: `translate(${b.x - a.x}px, ${b.y - a.y}px) scale(${to ? 0.35 : 0.6})`, opacity: to ? 0.25 : 0 },
    ],
    { duration: DURATION + 120, delay, easing: "ease-in", fill: "both" },
  );
  anim.onfinish = () => el.remove();
}

// Floating "−3" / "+2" over a unit.
function floatNumber(place, text, kind) {
  const el = document.createElement("span");
  el.className = `float-num ${kind}`;
  el.textContent = text;
  place.appendChild(el);
  const anim = el.animate(
    [{ transform: "translate(-50%, 0)", opacity: 1 }, { transform: "translate(-50%, -34px)", opacity: 0 }],
    { duration: 1100, easing: "ease-out", fill: "forwards" },
  );
  anim.onfinish = () => el.remove();
}

// --- spotlight: another player's card in the middle of the screen ---------------------------------

const spotlightQueue = [];
let spotlightBusy = false;

// `hold`: ms in the middle of the screen. `hideTarget`: hide the destination until the card lands
// (a played card / unit); off for a pile, which just pulses when the card arrives.
function enqueueSpotlight(card, selector, { hold = 900, hideTarget = true } = {}) {
  spotlightQueue.push({ card, selector, hold, hideTarget });
  const target = hideTarget ? document.querySelector(selector) : null;
  if (target) target.style.visibility = "hidden"; // shown when the card lands
  if (!spotlightBusy) nextSpotlight();
}

function nextSpotlight() {
  const item = spotlightQueue.shift();
  if (!item) {
    spotlightBusy = false;
    return;
  }
  spotlightBusy = true;
  const overlay = document.createElement("div");
  overlay.className = "spotlight";
  overlay.innerHTML = handCard(item.card, { still: true });
  document.body.appendChild(overlay);
  const cardEl = overlay.firstElementChild;
  const show = cardEl.animate(
    [{ transform: "scale(0.5)", opacity: 0 }, { transform: "scale(1.9)", opacity: 1 }],
    { duration: 260, easing: EASE, fill: "forwards" },
  );
  show.onfinish = () => {
    setTimeout(() => {
      const target = document.querySelector(item.selector); // looked up now: the board may have re-rendered
      const from = cardEl.getBoundingClientRect();
      const to = target ? target.getBoundingClientRect() : null;
      const a = center(from);
      const b = to ? center(to) : a;
      const scale = to ? Math.max(0.2, to.width / (from.width / 1.9)) : 1;
      const fly = cardEl.animate(
        [
          { transform: "scale(1.9)", opacity: 1 },
          { transform: `translate(${b.x - a.x}px, ${b.y - a.y}px) scale(${scale})`, opacity: to ? 0.9 : 0 },
        ],
        { duration: 420, easing: "ease-in", fill: "forwards" },
      );
      fly.onfinish = () => {
        overlay.remove();
        const landed = document.querySelector(item.selector);
        if (landed && item.hideTarget) {
          landed.style.visibility = "";
          popIn(landed.querySelector(".unit") || landed);
        } else if (landed) {
          landed.animate([{ transform: "scale(1)" }, { transform: "scale(1.18)" }, { transform: "scale(1)" }], { duration: 320 });
        }
        nextSpotlight();
      };
    }, item.hold);
  };
}

// --- after render ---------------------------------------------------------------------------------

// Call right after the board is re-rendered, with the snapshot taken before and the new view.
export function animateBoard(root, before, view) {
  if (!before || reducedMotion()) return;
  const spotlights = animatePlayed(root, before, view);
  animateUnits(root, before, view, spotlights);
  animateHand(root, before, view);
  animateMarkets(root, before, view);
}

const pileCount = (root, key) => Number(root.querySelector(`[data-pile="${key}"] b`)?.textContent || 0);
const pileGrew = (root, before, key) => before.piles.has(key) && pileCount(root, key) > before.piles.get(key).count;

function animatePlayed(root, before, view) {
  const spotlights = new Set();
  const seen = new Set();
  root.querySelectorAll("[data-played]").forEach((el) => {
    const uid = el.dataset.played;
    seen.add(uid);
    if (before.played.has(uid)) return;
    const from = before.hand.get(uid);
    const seat = Number(el.closest("[data-played-row]")?.dataset.playedRow);
    if (from) flyFrom(el, from); // you played it from your hand
    else if (seat !== view.you) {
      const card = view.players[seat]?.in_play.find((c) => c.uid === uid);
      if (card) {
        enqueueSpotlight(card, `[data-played="${uid}"]`);
        spotlights.add(uid);
      }
    } else popIn(el);
  });
  let i = 0;
  for (const [uid, old] of before.played) {
    if (seen.has(uid) || old.seat === undefined) continue;
    const key = `seat${old.seat}-discard`;
    const target = root.querySelector(`[data-pile="${key}"]`);
    if (target && pileGrew(root, before, key)) ghost(old.html, old.rect, target.getBoundingClientRect(), { delay: 60 * i++ }); // end of turn
  }
  return spotlights;
}

function animateUnits(root, before, view, spotlights) {
  const table = root.querySelector("[data-table]");
  const factor = table ? parseFloat(getComputedStyle(table).getPropertyValue("--unit-scale")) || 1 : 1;
  const units = new Map(boardUnits(view).map(({ unit }) => [unit.uid, unit]));
  const seen = new Set();
  root.querySelectorAll(".place[data-uid]").forEach((place) => {
    const uid = place.dataset.uid;
    const inner = place.querySelector(".unit");
    seen.add(uid);
    if (!inner) return;
    const old = before.units.get(uid);
    if (!old) {
      const fromHand = before.hand.get(uid);
      if (fromHand) flyFrom(inner, fromHand, { scale: 1.3, factor }); // you played it
      else if (Number(place.dataset.owner) !== view.you && units.get(uid) && !spotlights.has(uid)) {
        enqueueSpotlight(units.get(uid), `.place[data-uid="${uid}"]`); // another player's unit enters
      } else popIn(inner);
      return;
    }
    const moved = Math.abs(center(old.rect).x - center(inner.getBoundingClientRect()).x) > 2
      || Math.abs(center(old.rect).y - center(inner.getBoundingClientRect()).y) > 2;
    if (old.tier !== place.dataset.tier) {
      flyFrom(inner, old.rect, { factor, duration: 650 }); // tier up (or down)
      place.classList.add("tierup");
      setTimeout(() => place.classList.remove("tierup"), 1300);
    } else if (moved) flyFrom(inner, old.rect, { factor });
    const hp = Number(place.dataset.hp);
    if (hp < old.hp) {
      inner.animate(
        [{ transform: "translateX(0)" }, { transform: "translateX(-5px)" }, { transform: "translateX(5px)" }, { transform: "translateX(-3px)" }, { transform: "translateX(0)" }],
        { duration: 380 },
      );
      place.classList.add("hit");
      setTimeout(() => place.classList.remove("hit"), 700);
      floatNumber(place, `−${old.hp - hp}`, "damage");
    } else if (hp > old.hp) floatNumber(place, `+${hp - old.hp}`, "heal");
  });
  for (const [uid, old] of before.units) {
    if (seen.has(uid) || root.querySelector(`[data-hand-uid="${uid}"]`)) continue; // still here, or back in the hand
    const pile = root.querySelector(`[data-pile="seat${old.owner}-discard"]`);
    const destroyed = pile && pileGrew(root, before, `seat${old.owner}-discard`);
    ghost(old.html, old.rect, destroyed ? pile.getBoundingClientRect() : null, { tint: "var(--danger-bg)" });
  }
}

function animateHand(root, before, view) {
  if (!before.hand.size && !before.played.size) return; // nothing to compare with (first view of this seat)
  const deck = root.querySelector(`[data-pile="seat${view.you}-deck"]`);
  let i = 0;
  root.querySelectorAll("[data-hand-uid]").forEach((el) => {
    const uid = el.dataset.handUid;
    if (before.hand.has(uid)) return;
    const from = before.played.get(uid)?.rect || before.units.get(uid)?.rect; // taken back (undo) or bounced
    if (from) flyFrom(el, from);
    else if (deck) flyFrom(el, deck.getBoundingClientRect(), { scale: 0.4, delay: 80 * i++ }); // drawn
  });
}

function animateMarkets(root, before, view) {
  const seen = new Set();
  root.querySelectorAll("[data-mcard]").forEach((el) => {
    const uid = el.dataset.mcard;
    seen.add(uid);
    const old = before.cards.get(uid);
    if (old) {
      if (old.slot !== el.dataset.slot) flyFrom(el, old.rect); // slid to another slot (refresh)
      return;
    }
    const key = rowKey(el);
    const deck = key && before.piles.get(`${key}-deck`);
    const nowDeck = key && root.querySelector(`[data-pile="${key}-deck"] b`);
    if (!deck || !nowDeck || Number(nowDeck.textContent) >= deck.count) return; // e.g. switched private-market tab
    // Refresh: the new card comes out of the deck. Buy: it simply appears in the bought card's slot.
    if (pileGrew(root, before, `${key}-removed`)) flyFrom(el, deck.rect, { scale: 0.6 });
    else popIn(el, 250);
  });
  for (const [uid, old] of before.cards) {
    if (seen.has(uid)) continue;
    // Bought (shared, private or basic supply): it's now in the buyer's discard pile.
    const buyer = view.players.find((p) => p.discard.some((c) => c.uid === uid));
    if (buyer) {
      const card = buyer.discard.find((c) => c.uid === uid);
      enqueueSpotlight(card, `[data-pile="seat${buyer.seat}-discard"]`, { hold: buyer.seat === view.you ? 350 : 900, hideTarget: false });
      continue;
    }
    // Refresh (or discarded by a card): to the market's removed pile.
    if (old.row && pileGrew(root, before, `${old.row}-removed`)) {
      const target = root.querySelector(`[data-pile="${old.row}-removed"]`);
      if (target) ghost(old.html, old.rect, target.getBoundingClientRect());
    }
  }
}
