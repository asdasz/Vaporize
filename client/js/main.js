import { api } from "./api.js";
import { loadLocale } from "./i18n.js";
import { renderSetup } from "./setup.js";
import { rememberName, renderLobby, renderPlayerForm, renderStart } from "./lobby.js";
import { renderBoard } from "./board/board.js";
import { numberLabel, previewLine } from "./board/prompt.js";

const app = document.getElementById("app");

const store = {
  online: null, // {code, token} when playing in an online room (you only ever see your own seat)
  room: null, // the room's lobby view while it hasn't started
  roomVersion: null, // last room/game version seen (polling)
  roomCopied: false, // "Copied!" on the share button
  roomError: null, // error key shown in the lobby
  gameId: null,
  seat: 0, // seat we're viewing as (hot-seat)
  follow: true, // auto-switch to the current player
  view: null,
  error: null, // last illegal-action error {key, params}
  openMarket: "self", // private market shown: "self" or a seat number
  draft: null, // local, unsent answer for the pending prompt: {key, value, split}
  attacker: null, // uid of the own unit selected to attack
  removal: { open: false, peek: false, confirm: null }, // card-removal overlay
  swap: null, // chosen element swap {uid, from, to}, sent with the next play of that card
  swapEdit: null, // uid of the hand card whose swap panel is open
  eot: null, // {discards: [uid]} while the "before you end your turn" panel is open
  pileView: null, // {seat, which: "discard" | "removed"} while a pile overlay is open
  logOpen: true, // game log expanded
  bankEdit: null, // uid of the unit whose bank panel (143: keep gold on it) is open
};

// Reset the local draft whenever a new prompt appears.
function syncDraft(view) {
  const p = view.pending;
  const key = p && p.prompt ? `${p.card?.uid}:${p.step}` : null;
  if (!key) store.draft = null;
  else if (!store.draft || store.draft.key !== key) store.draft = { key, value: p.prompt.max, split: {}, cards: [] };
}

// Hand order is cosmetic and kept per game + seat in the browser (sessionStorage, memory fallback).
const memoryOrders = new Map();
const orderKey = () => `vaporize.handOrder.${store.online ? store.online.code : store.gameId}.${store.seat}`;

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

// Your token for an online room lives in this tab only (sessionStorage), so two tabs can be two players.
const memoryTokens = new Map();
const tokenKey = (code) => `vaporize.room.${code}`;

function loadToken(code) {
  try {
    return sessionStorage.getItem(tokenKey(code)) || memoryTokens.get(code) || null;
  } catch {
    return memoryTokens.get(code) || null;
  }
}

function saveToken(code, token) {
  memoryTokens.set(code, token);
  try {
    if (token) sessionStorage.setItem(tokenKey(code), token);
    else sessionStorage.removeItem(tokenKey(code));
  } catch {
    /* storage unavailable */
  }
}

function setUrl() {
  const params = new URLSearchParams();
  if (store.online) params.set("room", store.online.code);
  if (store.gameId) params.set("game", store.gameId);
  if (store.gameId && !store.follow) params.set("seat", String(store.seat));
  history.replaceState(null, "", params.toString() ? `?${params}` : location.pathname);
}

async function loadView() {
  if (store.online) {
    const { code, token } = store.online;
    const room = await api.roomView(code, token);
    store.roomVersion = room.version;
    if (room.status === "lobby") {
      store.room = room;
      return null;
    }
    store.room = null;
    const view = await api.roomGame(code, token);
    store.seat = view.you;
    store.follow = false;
    return view;
  }
  let view = await api.getView(store.gameId, store.seat);
  if (store.follow && view.phase !== "game_over" && view.current !== store.seat) {
    store.seat = view.current;
    view = await api.getView(store.gameId, store.seat);
  }
  return view;
}

async function refresh() {
  const view = await loadView();
  if (!view) {
    setUrl();
    drawLobby();
    return;
  }
  store.roomVersion = view.version;
  applyHandOrder(view);
  syncDraft(view);
  // Drop a chosen swap that's no longer possible (card played or gone, swap used, not our turn).
  const swapOptions = view.legal.element_swap?.options || {};
  if (store.swap && !swapOptions[store.swap.uid]) store.swap = null;
  if (store.swapEdit && !swapOptions[store.swapEdit]) store.swapEdit = null;
  if (store.bankEdit && !(view.legal.bank || {})[store.bankEdit]) store.bankEdit = null; // not your turn / unit gone
  store.view = view;
  setUrl();
  draw();
}

function draw() {
  app.onsubmit = null;
  renderBoard(app, store.view, store, handlers);
}

function drawLobby() {
  store.view = null;
  renderLobby(app, store.room, {
    copied: store.roomCopied,
    errorKey: store.roomError,
    onCopy: async (link) => {
      try {
        await navigator.clipboard.writeText(link);
      } catch {
        app.querySelector("[data-link]")?.select(); // no clipboard access: select it for Cmd+C
      }
      store.roomCopied = true;
      drawLobby();
    },
    onStart: () => roomCall(() => api.roomStart(store.online.code, store.online.token)),
    onClass: (classId) => roomCall(() => api.roomUpdate(store.online.code, store.online.token, { class_id: classId })),
    onLeave: async () => {
      const { code, token } = store.online;
      await api.roomLeave(code, token).catch(() => {});
      saveToken(code, null);
      showStart();
    },
  });
}

// A lobby request, then reload the room (or show the error in the lobby).
async function roomCall(fn) {
  try {
    await fn();
    store.roomError = null;
  } catch (err) {
    if (!err.key) return handleFailure(err);
    store.roomError = err.key;
  }
  await refresh().catch(handleFailure);
}

// Server errors: a 404 means the game is gone (e.g. server restarted without a save file).
function handleFailure(err) {
  if (store.online && (err.status === 404 || err.status === 403)) {
    const { code } = store.online;
    saveToken(code, null);
    if (err.status === 403) showJoin(code, "error.not_in_room"); // token no longer valid: join again
    else showStart(err.key === "error.room_not_found" ? "ui.lobby.room_gone" : "ui.setup.game_lost");
    return;
  }
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

let actionsInFlight = 0;

function act(action) {
  if (action.type === "play_card") {
    if (pendingPlays.has(action.card_uid)) return actionQueue;
    pendingPlays.add(action.card_uid);
  }
  actionsInFlight += 1;
  actionQueue = actionQueue
    .then(() => sendAction(action))
    .finally(() => {
      pendingPlays.delete(action.card_uid);
      actionsInFlight -= 1;
    });
  return actionQueue;
}

// Other windows (other players) act too: poll the game's version and reload the view when it
// changed. Skipped while our own action is on its way (it reloads anyway), while a card is being
// dragged (a re-render would cancel the drag) and while the tab is hidden.
const POLL_MS = 1000;
let polling = false;
const busy = () => actionsInFlight > 0 || app.dataset.dragging === "1";

async function poll() {
  const active = store.online ? store.view || store.room : store.gameId && store.view;
  if (polling || !active || document.hidden || busy()) return;
  polling = true;
  try {
    const { version } = store.online
      ? await api.roomVersion(store.online.code, store.online.token)
      : await api.getVersion(store.gameId);
    const seen = store.online ? store.roomVersion : store.view.version;
    if (version !== seen && !busy()) await refresh();
  } catch (err) {
    if (err.status === 404) handleFailure(err);
  } finally {
    polling = false;
  }
}

setInterval(poll, POLL_MS);
document.addEventListener("visibilitychange", poll);

async function sendAction(action) {
  if (!store.gameId && !store.online) return;
  try {
    const res = store.online
      ? await api.roomAct(store.online.code, store.online.token, action)
      : await api.act(store.gameId, action);
    store.error = res.ok ? null : res.error;
    if (res.ok && action.type === "end_turn") {
      store.openMarket = "self";
      store.attacker = null;
      store.removal = { open: false, peek: false, confirm: null };
    }
    await refresh();
  } catch (err) {
    handleFailure(err);
  }
}

function leaveScreens() {
  store.online = null;
  store.room = null;
  store.gameId = null;
  store.view = null;
  store.roomError = null;
  store.roomCopied = false;
}

async function classIds() {
  try {
    return (await api.listClasses()).classes;
  } catch {
    return ["mage"];
  }
}

// Start screen: Host game / Join game / local hot-seat test game.
function showStart(noticeKey = null) {
  leaveScreens();
  setUrl();
  renderStart(app, { noticeKey, onHost: () => showHost(), onJoin: () => showJoin(), onLocal: () => showSetup() });
}

async function showHost() {
  renderPlayerForm(app, {
    mode: "host",
    classes: await classIds(),
    onBack: () => showStart(),
    onSubmit: async ({ name, classId }) => {
      const { code, token } = await api.hostRoom(name, classId);
      rememberName(name);
      saveToken(code, token);
      await enterRoom(code, token);
    },
  });
}

async function showJoin(code = "", noticeKey = null) {
  leaveScreens();
  if (code) history.replaceState(null, "", `?room=${code}`);
  renderPlayerForm(app, {
    mode: "join",
    code,
    noticeKey,
    classes: await classIds(),
    onBack: () => showStart(),
    onSubmit: async ({ code: joinCode, name, classId }) => {
      const res = await api.joinRoom(joinCode, name, classId); // errors (room full, …) show in the form
      rememberName(name);
      saveToken(res.code, res.token);
      await enterRoom(res.code, res.token);
    },
  });
}

async function enterRoom(code, token) {
  leaveScreens();
  store.online = { code, token };
  store.follow = false;
  await refresh().catch(handleFailure);
}

function showSetup(noticeKey = null) {
  store.online = null;
  store.room = null;
  store.gameId = null;
  store.view = null;
  setUrl();
  renderSetup(app, {
    noticeKey,
    loadClasses: () => api.listClasses().then((r) => r.classes),
    onCreate: async (players, classes) => {
      const { game_id: gameId } = await api.createGame(players, classes);
      store.gameId = gameId;
      store.follow = true;
      store.error = null;
      await refresh();
    },
  });
}

const handlers = {
  playCard: (uid) => {
    const swap = store.swap && store.swap.uid === uid ? { from: store.swap.from, to: store.swap.to } : undefined;
    if (swap) store.swap = null;
    store.swapEdit = null;
    return act({ type: "play_card", seat: store.seat, card_uid: uid, swap });
  },
  swapOpen: (uid) => {
    store.swapEdit = store.swapEdit === uid ? null : uid;
    draw();
  },
  swapPick: (from, to) => {
    store.swap = { uid: store.swapEdit, from, to }; // only one card can carry the swap (once per turn)
    draw();
  },
  swapClear: () => {
    store.swap = null;
    draw();
  },
  swapClose: () => {
    store.swapEdit = null;
    draw();
  },
  endTurn: () => {
    const hand = store.view.players[store.view.you].hand || [];
    if (hand.some((c) => c.hand_eot)) {
      store.eot = { discards: [] }; // ask first: optional end-of-turn abilities of hand cards
      draw();
      return;
    }
    act({ type: "end_turn", seat: store.seat });
  },
  eotToggle: (uid, on) => {
    const set = new Set(store.eot?.discards || []);
    if (on) set.add(uid);
    else set.delete(uid);
    store.eot = { discards: [...set] };
  },
  endTurnConfirm: () => {
    const discards = store.eot?.discards || [];
    store.eot = null;
    act({ type: "end_turn", seat: store.seat, hand_discards: discards });
  },
  endTurnCancel: () => {
    store.eot = null;
    draw();
  },
  resetCards: () => {
    if (store.draft) store.draft.cards = [];
    draw();
  },
  undo: () => act({ type: "undo", seat: store.seat }),
  cancelTurn: () => act({ type: "cancel_turn", seat: store.seat }),
  respond: (answer) => act({ type: "respond", seat: store.seat, answer }),
  develop: (uid, pay = "inf") => act({ type: "develop", seat: store.seat, unit_uid: uid, pay }),
  bankOpen: (uid) => {
    store.bankEdit = store.bankEdit === uid ? null : uid;
    draw();
  },
  bank: (uid, amount) => act({ type: "bank", seat: store.seat, unit_uid: uid, amount }),
  removeCard: (uid) => {
    store.removal = { open: false, peek: false, confirm: null };
    return act({ type: "remove_card", seat: store.seat, card_uid: uid });
  },
  removal: (changes) => {
    const base = changes.open === true ? { open: true, peek: false, confirm: null } : store.removal;
    store.removal = { ...base, ...changes };
    if (!store.removal.open) store.removal = { open: false, peek: false, confirm: null };
    draw();
  },
  pickRemove: (uid) => handlers.removal({ confirm: uid }), // every removal asks for confirmation
  buy: (market, slot, pay = "inf") => act({ type: "buy", seat: store.seat, market, slot, pay }),
  toggleCard: (uid) => {
    if (!store.draft) return;
    const cards = new Set(store.draft.cards || []);
    if (cards.has(uid)) cards.delete(uid);
    else cards.add(uid);
    store.draft.cards = [...cards];
    draw();
  },
  confirmCards: () => store.draft && handlers.respond([...(store.draft.cards || [])]),
  refresh: (market) => act({ type: "refresh", seat: store.seat, market }),
  selectAttacker: (uid) => {
    store.attacker = store.attacker === uid ? null : uid;
    draw();
  },
  attack: (targetUid) => {
    const attacker = store.attacker;
    store.attacker = null;
    if (attacker) act({ type: "attack", seat: store.seat, unit_uid: attacker, target_uid: targetUid });
  },
  cancelChoice: () => act({ type: "cancel_choice", seat: store.seat }),
  pickUnit: (uid) => {
    const prompt = store.view?.pending?.prompt;
    if (!prompt) return;
    if (prompt.kind === "choose_unit") handlers.respond(uid);
    else if (prompt.kind === "split_damage") handlers.splitAdjust(uid, 1);
  },
  draftNumber: (value, root) => {
    if (!store.draft) return;
    store.draft.value = value;
    const prompt = store.view.pending.prompt;
    const label = root.querySelector("[data-number-label]");
    if (label) label.textContent = numberLabel(prompt, value);
    const preview = root.querySelector("[data-number-preview]");
    if (preview) preview.textContent = previewLine(store.view, value);
  },
  confirmNumber: () => store.draft && handlers.respond(store.draft.value),
  splitAdjust: (uid, delta) => {
    const prompt = store.view?.pending?.prompt;
    if (!store.draft || !prompt) return;
    const split = store.draft.split;
    const assigned = Object.values(split).reduce((a, b) => a + b, 0);
    if (delta > 0 && assigned >= prompt.total) return;
    split[uid] = Math.max(0, (split[uid] || 0) + delta);
    if (!split[uid]) delete split[uid];
    draw();
  },
  confirmSplit: () => store.draft && handlers.respond({ ...store.draft.split }),
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
  showMarket: (key) => {
    store.openMarket = key; // buttons side by side: always switch, never hide
    draw();
  },
  viewPile: (pile) => {
    store.pileView = pile;
    draw();
  },
  toggleLog: () => {
    store.logOpen = !store.logOpen;
    draw();
  },
  setHandOrder: (uids) => {
    if (uids) {
      saveHandOrder(uids);
      applyHandOrder(store.view);
    }
    draw();
  },
  newGame: () => showStart(),
};

async function start() {
  await loadLocale("en");
  const params = new URLSearchParams(location.search);
  const roomCode = (params.get("room") || "").toUpperCase();
  if (roomCode) {
    const token = loadToken(roomCode);
    return token ? enterRoom(roomCode, token) : showJoin(roomCode); // a shared link: join that room
  }
  const gameId = params.get("game");
  if (!gameId) return showStart();
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
