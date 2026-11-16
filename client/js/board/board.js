// Composes the whole board from region modules and wires up events (delegated on the root).
import { playerPanel } from "./panel.js";
import { privateMarkets, sharedMarket } from "./markets.js";
import { sidebar } from "./sidebar.js";
import { tierTable } from "./tiers.js";
import { topbar } from "./topbar.js";
import { vpTrack } from "./vptrack.js";

export function renderBoard(root, view, store, handlers) {
  root.innerHTML = `
    <div class="layout">
      <main class="main">
        ${topbar(view, store)}
        ${vpTrack(view)}
        ${tierTable(view)}
        ${sharedMarket(view)}
        ${privateMarkets(view, store)}
        ${playerPanel(view, store)}
      </main>
      <aside class="side">${sidebar(view)}</aside>
    </div>`;

  root.onclick = (event) => {
    const el = event.target.closest("[data-action]");
    if (!el || el.disabled) return;
    const action = el.dataset.action;
    if (action === "play") handlers.playCard(el.dataset.uid);
    else if (action === "end-turn") handlers.endTurn();
    else if (action === "market") handlers.toggleMarket(Number(el.dataset.seat) === view.you ? "self" : Number(el.dataset.seat));
    else if (action === "new-game") handlers.newGame();
  };
  bindHandDrag(root, handlers);

  root.onchange = (event) => {
    const el = event.target.closest("[data-change]");
    if (!el) return;
    if (el.dataset.change === "seat") handlers.setSeat(Number(el.value));
    else if (el.dataset.change === "follow") handlers.setFollow(el.checked);
  };
}

// Drag a hand card left/right to move it: the other cards shift to make room (live, animated).
// Hand order is cosmetic and client-side only.
function bindHandDrag(root, handlers) {
  let dragged = null; // the hand card element being dragged
  let dropped = false;
  const handEl = () => root.querySelector(".hand");
  const handCards = () => [...handEl().querySelectorAll("[data-hand-uid]")];

  // Element to insert the dragged card before (works for wrapped rows too); null = end of the cards.
  function insertBeforeFor(x, y) {
    for (const card of handCards()) {
      if (card === dragged) continue;
      const r = card.getBoundingClientRect();
      if (y < r.top || (y < r.bottom && x < r.left + r.width / 2)) return card;
    }
    return null;
  }

  // FLIP animation: cards jump to their new place, then slide there from the old one.
  function moveWithAnimation(ref) {
    const hand = handEl();
    const end = hand.querySelector(".end-turn");
    const target = ref || end;
    if (target === dragged || dragged.nextElementSibling === target) return;
    const cards = handCards();
    const before = new Map(cards.map((c) => [c, c.getBoundingClientRect().left]));
    hand.insertBefore(dragged, target);
    for (const card of cards) {
      if (card === dragged) continue;
      const dx = before.get(card) - card.getBoundingClientRect().left;
      if (!dx) continue;
      card.style.transition = "none";
      card.style.transform = `translateX(${dx}px)`;
      card.getBoundingClientRect(); // force reflow
      card.style.transition = "transform 160ms ease";
      card.style.transform = "";
    }
  }

  root.ondragstart = (event) => {
    const el = event.target.closest("[data-hand-uid]");
    if (!el) return;
    dragged = el;
    dropped = false;
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", el.dataset.handUid);
    requestAnimationFrame(() => el.classList.add("dragging"));
  };
  root.ondragover = (event) => {
    if (!dragged || !event.target.closest(".hand")) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    moveWithAnimation(insertBeforeFor(event.clientX, event.clientY));
  };
  root.ondrop = (event) => {
    if (!dragged || !event.target.closest(".hand")) return;
    event.preventDefault();
    dropped = true;
  };
  root.ondragend = () => {
    if (!dragged) return;
    const order = handCards().map((c) => c.dataset.handUid);
    dragged = null;
    // Dropped inside the hand: keep the new order. Cancelled: re-render the old one.
    handlers.setHandOrder(dropped ? order : null);
  };
}
