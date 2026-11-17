// Market animations (FLIP): cards slide to their new slot, new cards come out of the deck pile,
// cards that left the row fly to the removed pile (refresh) or to the buyer's panel (buy).
const DURATION = 380;

const reducedMotion = () => window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// Call before the board is re-rendered.
export function snapshotMarkets(root) {
  if (!root.querySelectorAll) return null;
  const cards = new Map();
  root.querySelectorAll("[data-mcard]").forEach((el) => {
    cards.set(el.dataset.mcard, { rect: el.getBoundingClientRect(), html: el.outerHTML, row: el.closest(".market-row") });
  });
  const piles = new Map();
  root.querySelectorAll("[data-pile]").forEach((el) =>
    piles.set(el.dataset.pile, { rect: el.getBoundingClientRect(), count: Number(el.querySelector("b")?.textContent || 0) }),
  );
  return { cards, piles };
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
export function animateMarkets(root, before) {
  if (!before || reducedMotion()) return;
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
    const target = wentToRemoved
      ? root.querySelector(`[data-pile="${key}-removed"]`)
      : root.querySelector(".panel .stats-row") || root.querySelector(".panel");
    if (target) ghost(old.html, old.rect, target.getBoundingClientRect());
  }
}
