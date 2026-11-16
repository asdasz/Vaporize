import { api } from "./api.js";
import { loadLocale } from "./i18n.js";
import { renderSetup } from "./setup.js";
import { renderBoard } from "./board/board.js";

const app = document.getElementById("app");

const store = {
  gameId: null,
  seat: 0, // seat we're viewing as (hot-seat)
  follow: true, // auto-switch to the current player
  view: null,
  error: null, // last illegal-action error {key, params}
  openMarket: "self", // "self" | seat number | null (all hidden)
};

// Hand order is cosmetic and kept per game + seat in the browser (sessionStorage, memory fallback).
const memoryOrders = new Map();
const orderKey = () => `vaporize.handOrder.${store.gameId}.${store.seat}`;

function loadHandOrder() {
  try {
    const saved = sessionStorage.getItem(orderKey());
    if (saved) return JSON.parse(saved);
  } catch {
    /* storage unavailable */
  }
  return memoryOrders.get(orderKey()) || [];
}

function saveHandOrder(uids) {
  memoryOrders.set(orderKey(), uids);
  try {
    sessionStorage.setItem(orderKey(), JSON.stringify(uids));
  } catch {
    /* storage unavailable */
  }
}

// Sort the viewer's hand by the saved order; new cards go to the right in draw order.
function applyHandOrder(view) {
  const hand = view.players[view.you].hand;
  if (!hand) return;
  const saved = new Map(loadHandOrder().map((uid, i) => [uid, i]));
  const rank = new Map(hand.map((c, i) => [c.uid, saved.has(c.uid) ? saved.get(c.uid) : 1e6 + i]));
  hand.sort((a, b) => rank.get(a.uid) - rank.get(b.uid));
  saveHandOrder(hand.map((c) => c.uid));
}

function setUrl() {
  const params = new URLSearchParams();
  if (store.gameId) params.set("game", store.gameId);
  if (!store.follow) params.set("seat", String(store.seat));
  history.replaceState(null, "", params.toString() ? `?${params}` : location.pathname);
}

async function refresh() {
  let view = await api.getView(store.gameId, store.seat);
  if (store.follow && view.phase !== "game_over" && view.current !== store.seat) {
    store.seat = view.current;
    view = await api.getView(store.gameId, store.seat);
  }
  applyHandOrder(view);
  store.view = view;
  setUrl();
  draw();
}

function draw() {
  renderBoard(app, store.view, store, handlers);
}

async function act(action) {
  const res = await api.act(store.gameId, action);
  store.error = res.ok ? null : res.error;
  if (res.ok && action.type === "end_turn") store.openMarket = "self";
  await refresh();
}

function showSetup() {
  store.gameId = null;
  setUrl();
  renderSetup(app, {
    onCreate: async (players) => {
      const { game_id: gameId } = await api.createGame(players);
      store.gameId = gameId;
      store.follow = true;
      store.error = null;
      await refresh();
    },
  });
}

const handlers = {
  playCard: (uid) => act({ type: "play_card", seat: store.seat, card_uid: uid }),
  endTurn: () => act({ type: "end_turn", seat: store.seat }),
  setSeat: async (seat) => {
    store.seat = seat;
    store.follow = false;
    store.error = null;
    store.openMarket = "self";
    await refresh();
  },
  setFollow: async (on) => {
    store.follow = on;
    await refresh();
  },
  toggleMarket: (key) => {
    store.openMarket = String(store.openMarket) === String(key) ? null : key;
    draw();
  },
  setHandOrder: (uids) => {
    if (uids) {
      saveHandOrder(uids);
      applyHandOrder(store.view);
    }
    draw();
  },
  newGame: () => showSetup(),
};

async function start() {
  await loadLocale("en");
  const params = new URLSearchParams(location.search);
  const gameId = params.get("game");
  if (!gameId) return showSetup();
  store.gameId = gameId;
  if (params.has("seat")) {
    store.seat = Number(params.get("seat"));
    store.follow = false;
  }
  try {
    await refresh();
  } catch {
    showSetup();
  }
}

start();
