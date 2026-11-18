// Composes the whole board from region modules and wires up events (delegated on the root).
import { t } from "../i18n.js";
import { animateMarkets, snapshotMarkets } from "./animate.js";
import { playerPanel } from "./panel.js";
import { removalOverlay } from "./removal.js";
import { privateMarkets, sharedMarket } from "./markets.js";
import { sidebar } from "./sidebar.js";
import { tierTable } from "./tiers.js";
import { topbar } from "./topbar.js";
import { vpTrack } from "./vptrack.js";

let lastGame = null;

export function renderBoard(root, view, store, handlers) {
  const before = lastGame === `${view.game_id}:${view.you}` ? snapshotMarkets(root) : null;
  lastGame = `${view.game_id}:${view.you}`;
  root.innerHTML = `
    <div class="layout">
      <main class="main">
        ${topbar(view, store)}
        ${vpTrack(view)}
        ${tierTable(view, store)}
        ${sharedMarket(view)}
        ${privateMarkets(view, store)}
        ${playerPanel(view, store)}
      </main>
      <aside class="side">${sidebar(view)}</aside>
    </div>
    <div class="play-zone" data-ok="${t("ui.panel.play_zone")}" data-blocked="${t("ui.panel.play_zone_blocked")}"></div>
    ${removalOverlay(view, store)}`;
  animateMarkets(root, before);

  root.onclick = (event) => {
    const el = event.target.closest("[data-action]");
    if (!el && store.attacker) handlers.selectAttacker(null);  // click elsewhere: drop the attacker selection
    if (!el || el.disabled) return;
    const action = el.dataset.action;
    if (action === "close-remove-backdrop") {
      if (!event.target.closest("[data-stop]")) handlers.removal({ open: false }); // click outside the dialog
      return;
    }
    if (action === "end-turn") handlers.endTurn();
    else if (action === "undo") handlers.undo();
    else if (action === "target") handlers.pickUnit(el.dataset.uid);
    else if (action === "develop") handlers.develop(el.dataset.uid);
    else if (action === "remove-card") handlers.removeCard(el.dataset.uid);
    else if (action === "open-remove") handlers.removal({ open: true });
    else if (action === "swap-open") handlers.swapOpen(el.dataset.uid);
    else if (action === "swap-pick") handlers.swapPick(el.dataset.from, el.dataset.to);
    else if (action === "swap-clear") handlers.swapClear();
    else if (action === "swap-close") handlers.swapClose();
    else if (action === "close-remove") handlers.removal({ open: false });
    else if (action === "peek-on") handlers.removal({ peek: true });
    else if (action === "peek-off") handlers.removal({ peek: false });
    else if (action === "pick-remove") handlers.pickRemove(el.dataset.uid);
    else if (action === "confirm-remove") handlers.removeCard(el.dataset.uid);
    else if (action === "confirm-no") handlers.removal({ confirm: null });
    else if (action === "choose-option") handlers.respond(Number(el.dataset.value));
    else if (action === "buy-vp") handlers.buy(el.dataset.market, Number(el.dataset.slot), "vp");
    else if (action === "buy") handlers.buy(el.dataset.market, Number(el.dataset.slot));
    else if (action === "toggle-card") handlers.toggleCard(el.dataset.uid);
    else if (action === "confirm-cards") handlers.confirmCards();
    else if (action === "refresh") handlers.refresh(el.dataset.market);
    else if (action === "select-attacker") handlers.selectAttacker(el.dataset.uid);
    else if (action === "attack-target") handlers.attack(el.dataset.uid);
    else if (action === "split") handlers.splitAdjust(el.dataset.uid, Number(el.dataset.delta));
    else if (action === "confirm-number") handlers.confirmNumber();
    else if (action === "confirm-split") handlers.confirmSplit();
    else if (action === "choose-card") handlers.respond(el.dataset.uid);
    else if (action === "skip-choice") handlers.respond(null);
    else if (action === "cancel-choice") handlers.cancelChoice();
    else if (action === "cancel-turn") handlers.cancelTurn();
    else if (action === "market") handlers.toggleMarket(Number(el.dataset.seat) === view.you ? "self" : Number(el.dataset.seat));
    else if (action === "new-game") handlers.newGame();
  };
  bindHandDrag(root, handlers);
  document.onkeydown = (event) => {
    if (event.key === "Escape" && store.removal?.open) handlers.removal({ open: false });
  };

  root.oninput = (event) => {
    const el = event.target.closest("[data-input='number']");
    if (el) handlers.draftNumber(Number(el.value), root);
  };

  root.onchange = (event) => {
    const el = event.target.closest("[data-change]");
    if (!el) return;
    if (el.dataset.change === "seat") handlers.setSeat(Number(el.value));
    else if (el.dataset.change === "follow") handlers.setFollow(el.checked);
  };
}

// Hand drag and drop:
// - drag left/right inside the hand to move a card; the other cards shift to make room (cosmetic, client-side)
// - drag a card up and release it anywhere on the screen above the hand to play it
function bindHandDrag(root, handlers) {
  let dragged = null; // the hand card element being dragged
  let intent = null; // "reorder" | "play" | null (cancelled)
  const handEl = () => root.querySelector(".hand");
  const zoneEl = () => root.querySelector(".play-zone");
  const handCards = () => [...handEl().querySelectorAll("[data-hand-uid]")];
  const isAboveHand = (y) => y < handEl().getBoundingClientRect().top - 8;

  // Element to insert the dragged card before (works for wrapped rows too); null = end of the hand.
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
    if (ref === dragged || dragged.nextElementSibling === ref) return;
    if (ref === null && dragged.nextElementSibling === null) return;
    const cards = handCards();
    const before = new Map(cards.map((c) => [c, c.getBoundingClientRect().left]));
    handEl().insertBefore(dragged, ref);
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

  // The drop zone covers the whole viewport above the hand (fixed overlay).
  function sizeZone() {
    const zone = zoneEl();
    if (!zone || !handEl()) return;
    const top = Math.min(handEl().getBoundingClientRect().top - 8, window.innerHeight);
    zone.style.height = `${Math.max(0, top)}px`;
  }

  function showZone(on) {
    const zone = zoneEl();
    if (!zone) return;
    if (on) {
      const ok = dragged.dataset.playable === "1";
      zone.classList.toggle("blocked", !ok);
      zone.textContent = ok ? zone.dataset.ok : zone.dataset.blocked;
      sizeZone();
    }
    zone.classList.toggle("visible", on);
  }

  root.ondragstart = (event) => {
    const el = event.target.closest("[data-hand-uid]");
    if (!el) return;
    dragged = el;
    intent = null;
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", el.dataset.handUid);
    requestAnimationFrame(() => {
      el.classList.add("dragging");
      showZone(true);
    });
  };
  document.ondragover = (event) => {
    if (!dragged || !handEl()) return;
    sizeZone();
    if (isAboveHand(event.clientY)) {
      event.preventDefault();
      event.dataTransfer.dropEffect = dragged.dataset.playable === "1" ? "move" : "none";
      zoneEl()?.classList.add("armed");
      return;
    }
    zoneEl()?.classList.remove("armed");
    if (!event.target.closest(".hand")) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    moveWithAnimation(insertBeforeFor(event.clientX, event.clientY));
  };
  document.ondrop = (event) => {
    if (!dragged || !handEl()) return;
    if (isAboveHand(event.clientY)) intent = dragged.dataset.playable === "1" ? "play" : null;
    else if (event.target.closest(".hand")) intent = "reorder";
    else return;
    event.preventDefault();
  };
  root.ondragend = () => {
    if (!dragged) return;
    const uid = dragged.dataset.handUid;
    const order = handCards().map((c) => c.dataset.handUid);
    dragged = null;
    showZone(false);
    zoneEl()?.classList.remove("armed");
    if (intent === "play") handlers.playCard(uid);
    else handlers.setHandOrder(intent === "reorder" ? order : null);
  };
}
