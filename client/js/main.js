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

// Server errors: a 404 means the game is gone (e.g. server restarted without a save file).
function handleFailure(err) {
  if (err.status === 404) {
    showSetup("ui.setup.game_lost");
    return;
  }
  store.error = { key: "ui.errors.connection", params: {} };
  if (store.view) draw();
  else showSetup("ui.errors.connection");
}

// Actions are sent one at a time, in order. Fast clicks/drags are queued instead of racing
// each other; the same card can't be queued twice.
let actionQueue = Promise.resolve();
const pendingPlays = new Set();

function act(action) {
  if (action.type === "play_card") {
    if (pendingPlays.has(action.card_uid)) return actionQueue;
    pendingPlays.add(action.card_uid);
  }
  actionQueue = actionQueue.then(() => sendAction(action)).finally(() => pendingPlays.delete(action.card_uid));
  return actionQueue;
}

async function sendAction(action) {
  if (!store.gameId) return;
  try {
    const res = await api.act(store.gameId, action);
    store.error = res.ok ? null : res.error;
    if (res.ok && action.type === "end_turn") store.openMarket = "self";
    await refresh();
  } catch (err) {
    handleFailure(err);
  }
}

function showSetup(noticeKey = null) {
  store.gameId = null;
  store.view = null;
  setUrl();
  renderSetup(app, {
    noticeKey,
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
  undo: () => act({ type: "undo", seat: store.seat }),
  cancelTurn: () => act({ type: "cancel_turn", seat: store.seat }),
  setSeat: async (seat) => {
    store.seat = seat;
    store.follow = false;
    store.error = null;
    store.openMarket = "self";
    await refresh().catch(handleFailure);
  },
  setFollow: async (on) => {
    store.follow = on;
    await refresh().catch(handleFailure);
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
  } catch (err) {
    handleFailure(err);
  }
}

start();
