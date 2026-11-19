// Board animations (FLIP).
// Markets: cards slide to their new slot, new cards come out of the deck pile, cards that left the row
// fly to the removed pile (refresh) or to the buyer's discard pile (buy).
// Played cards: a played hand card slides into the played row; at end of turn the played cards fly
// to their owner's discard pile together.
const DURATION = 380;

const reducedMotion = () => window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// Call before the board is re-rendered.
export function snapshotBoard(root) {
  if (!root.querySelectorAll) return null;
  const cards = new Map();
  root.querySelectorAll("[data-mcard]").forEach((el) => {
    cards.set(el.dataset.mcard, { rect: el.getBoundingClientRect(), html: el.outerHTML, row: el.closest(".market-row") });
  });
  const piles = new Map();
  root.querySelectorAll("[data-pile]").forEach((el) =>
    piles.set(el.dataset.pile, { rect: el.getBoundingClientRect(), count: Number(el.querySelector("b")?.textContent || 0) }),
  );
  const played = new Map();
  root.querySelectorAll("[data-played]").forEach((el) =>
    played.set(el.dataset.played, { rect: el.getBoundingClientRect(), html: el.outerHTML, seat: el.closest("[data-played-row]")?.dataset.playedRow }),
  );
  const hand = new Map();
  root.querySelectorAll("[data-hand-uid]").forEach((el) => hand.set(el.dataset.handUid, el.getBoundingClientRect()));
  return { cards, piles, played, hand };
}

function rowKey(el) {
  const pile = el.closest(".market-row")?.querySelector("[data-pile$='-deck']");
  return pile ? pile.dataset.pile.replace(/-deck$/, "") : null;
}

function flyFrom(el, from) {
  const to = el.getBoundingClientRect();
  const dx = from.left - to.left;
  const dy = from.top - to.top;
  if (!dx && !dy) return;
  el.style.transition = "none";
  el.style.transform = `translate(${dx}px, ${dy}px)`;
  el.getBoundingClientRect(); // force reflow
  el.style.transition = `transform ${DURATION}ms ease, opacity ${DURATION}ms ease`;
  el.style.transform = "";
}

function ghost(html, from, to) {
  const holder = document.createElement("div");
  holder.innerHTML = html;
  const el = holder.firstElementChild;
  Object.assign(el.style, {
    position: "fixed", left: `${from.left}px`, top: `${from.top}px`, width: `${from.width}px`, height: `${from.height}px`,
    margin: "0", zIndex: "60", pointerEvents: "none", transition: `transform ${DURATION}ms ease, opacity ${DURATION}ms ease`,
  });
  document.body.appendChild(el);
  el.getBoundingClientRect();
  const dx = to.left + to.width / 2 - (from.left + from.width / 2);
  const dy = to.top + to.height / 2 - (from.top + from.height / 2);
  el.style.transform = `translate(${dx}px, ${dy}px) scale(0.5)`;
  el.style.opacity = "0.2";
  setTimeout(() => el.remove(), DURATION + 50);
}

// Call right after the board is re-rendered, with the snapshot taken before.
export function animateBoard(root, before) {
  if (!before || reducedMotion()) return;
  animatePlayed(root, before);
  animateMarkets(root, before);
}

const pileCount = (root, key) => Number(root.querySelector(`[data-pile="${key}"] b`)?.textContent || 0);

function animatePlayed(root, before) {
  const seen = new Set();
  root.querySelectorAll("[data-played]").forEach((el) => {
    const uid = el.dataset.played;
    seen.add(uid);
    const from = before.hand.get(uid);
    if (from && !before.played.has(uid)) flyFrom(el, from); // just played from the hand
  });
  for (const [uid, old] of before.played) {
    if (seen.has(uid) || old.seat === undefined) continue;
    const key = `seat${old.seat}-discard`;
    const target = root.querySelector(`[data-pile="${key}"]`);
    const grew = before.piles.has(key) && pileCount(root, key) > before.piles.get(key).count;
    if (target && grew) ghost(old.html, old.rect, target.getBoundingClientRect()); // end of turn: to the discard pile
  }
}

function animateMarkets(root, before) {
  const seen = new Set();
  root.querySelectorAll("[data-mcard]").forEach((el) => {
    const uid = el.dataset.mcard;
    seen.add(uid);
    const old = before.cards.get(uid);
    if (old) {
      flyFrom(el, old.rect); // slid to another slot
      return;
    }
    const key = rowKey(el);
    const deck = key && before.piles.get(`${key}-deck`);
    const nowDeck = key && root.querySelector(`[data-pile="${key}-deck"] b`);
    // Only when this market was on screen before and its deck got smaller (not when switching market tabs).
    if (deck && nowDeck && Number(nowDeck.textContent) < deck.count) {
      el.style.opacity = "0";
      flyFrom(el, deck.rect); // revealed from the deck
      requestAnimationFrame(() => (el.style.opacity = ""));
    }
  });
  for (const [uid, old] of before.cards) {
    if (seen.has(uid)) continue;
    const key = old.row?.querySelector("[data-pile$='-deck']")?.dataset.pile.replace(/-deck$/, "");
    if (!key || !root.querySelector(`[data-pile="${key}-deck"]`)) continue; // that market isn't shown any more
    const removedNow = root.querySelector(`[data-pile="${key}-removed"] b`);
    const removedBefore = before.piles.get(`${key}-removed`);
    const wentToRemoved = removedNow && removedBefore && Number(removedNow.textContent) > removedBefore.count;
    // Bought: to the discard pile that grew (the buyer's), else the bottom panel.
    const discard = [...root.querySelectorAll("[data-pile$='-discard']")].find(
      (el) => before.piles.has(el.dataset.pile) && pileCount(root, el.dataset.pile) > before.piles.get(el.dataset.pile).count,
    );
    const target = wentToRemoved ? root.querySelector(`[data-pile="${key}-removed"]`) : discard || root.querySelector(".panel");
    if (target) ghost(old.html, old.rect, target.getBoundingClientRect());
  }
}
