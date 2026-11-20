// Hold a card (mouse or finger down, without moving) to see it big in the middle of the screen with its
// whole text; release to close. Works for hand, market, played and table cards, piles and prompt choices.
// Also marks card texts that don't fit with "…" (markClipped).
import { handCard } from "./card.js";
import { boardUnits } from "./util.js";

const HOLD_MS = 450;
const MOVE_TOLERANCE = 6; // px; moving more (e.g. starting a drag) cancels the hold
const CARD_SELECTOR = "[data-card], [data-mcard], [data-played], .place[data-uid]";

let timer = null;
let start = null;
let overlay = null;
let swallowClick = false;
let bound = false;

// Every card the viewer can see, by uid.
function findCard(view, uid) {
  if (!view || !uid) return null;
  const pools = [];
  for (const p of view.players) {
    pools.push(p.hand || [], p.in_play, p.discard, p.removed, p.private_market.row.filter(Boolean).map((e) => e.card));
  }
  pools.push(view.shared_market.row.filter(Boolean).map((e) => e.card));
  if (view.basic_supply?.card) pools.push([view.basic_supply.card]);
  pools.push(boardUnits(view).map((x) => x.unit));
  const options = view.pending?.prompt?.options;
  if (Array.isArray(options)) pools.push(options.filter((o) => o && typeof o === "object"));
  if (view.pending?.card) pools.push([view.pending.card]);
  for (const pool of pools) {
    const card = pool.find((c) => c && c.uid === uid);
    if (card) return card;
  }
  return null;
}

const uidOf = (el) => el.dataset.card || el.dataset.mcard || el.dataset.played || el.dataset.uid;

function cancel() {
  clearTimeout(timer);
  timer = null;
  start = null;
}

function close() {
  cancel();
  if (overlay) {
    overlay.remove();
    overlay = null;
  }
}

function open(card) {
  close();
  overlay = document.createElement("div");
  overlay.className = "zoom-overlay";
  overlay.innerHTML = handCard(card, { still: true }).replace('class="hcard', 'class="hcard zoomed');
  document.body.appendChild(overlay);
  overlay.firstElementChild.animate(
    [{ transform: "scale(0.6)", opacity: 0 }, { transform: "scale(1)", opacity: 1 }],
    { duration: 160, easing: "ease-out" },
  );
  swallowClick = true; // releasing after a hold must not also buy / select the card
}

// `getView` returns the current view (cards are looked up by uid when the hold completes).
export function bindZoom(getView) {
  if (bound) return;
  bound = true;
  document.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    const el = event.target.closest(CARD_SELECTOR);
    if (!el || event.target.closest("button, select, input")) return;
    start = { x: event.clientX, y: event.clientY };
    clearTimeout(timer);
    timer = setTimeout(() => {
      const card = findCard(getView(), uidOf(el));
      if (card) open(card);
    }, HOLD_MS);
  });
  document.addEventListener("pointermove", (event) => {
    if (start && Math.hypot(event.clientX - start.x, event.clientY - start.y) > MOVE_TOLERANCE) cancel();
  });
  document.addEventListener("pointerup", close);
  document.addEventListener("pointercancel", close);
  document.addEventListener("dragstart", close);
  window.addEventListener("blur", close);
  document.addEventListener("contextmenu", (event) => {
    if (overlay) event.preventDefault(); // long press on touch screens
  });
  document.addEventListener(
    "click",
    (event) => {
      if (!swallowClick) return;
      swallowClick = false;
      event.stopPropagation();
      event.preventDefault();
    },
    true,
  );
  document.addEventListener("pointerdown", () => (swallowClick = false), true); // a fresh press clears it
}

// Card texts cut off by their box get a "…" marker (the hold shows the rest).
export function markClipped(root) {
  root.querySelectorAll(".hcard .text, .mcard .mtext").forEach((el) => {
    el.classList.toggle("clipped", el.scrollHeight > el.clientHeight + 1);
  });
}
