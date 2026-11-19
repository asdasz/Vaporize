// The table: tiers as concentric ellipses (T1 outside, shared T4 in the middle). Each player's units sit
// on the rings in their own direction (you at the bottom, the others clockwise around the table).
// Card border = owner colour. Positions are computed after render from the table's real size.
import { t } from "../i18n.js";
import { emptySlot, miniUnit } from "./card.js";
import { myPrompt } from "./util.js";

const UNIT_W = 100; // unit card size at scale 1 (cards shrink when the table is small)
const UNIT_H = 68;
const GAP = 8;
const LABEL_ANGLE = 135; // lower left: never a seat direction

// Direction (degrees, screen coordinates: 0 = right, 90 = down) of each seat, relative to the viewer.
const ANGLES = { 1: [90], 2: [90, 270], 3: [90, 240, 300], 4: [90, 180, 270, 0] };

export const relativeSeat = (view, seat) => (seat - view.you + view.players.length) % view.players.length;

// Units that the pending prompt lets us pick, and split damage assigned so far.
function targetInfo(view, store) {
  const prompt = myPrompt(view);
  const targets = new Set(prompt && ["choose_unit", "split_damage"].includes(prompt.kind) ? prompt.options : []);
  const split = (prompt && prompt.kind === "split_damage" && store.draft && store.draft.split) || {};
  const attacks = prompt ? {} : view.legal.attacks || {};
  const attacker = store.attacker && attacks[store.attacker] ? store.attacker : null;
  const resource = view.players[view.you].resource.key;
  const withResource = (obj) => Object.fromEntries(Object.entries(obj || {}).map(([uid, v]) => [uid, { ...v, resource }]));
  return {
    targets, split, develop: view.legal.develop || {}, attacks, attacker, attackTargets: new Set(attacker ? attacks[attacker] : []),
    developResource: withResource(view.legal.develop_resource), bank: withResource(view.legal.bank),
  };
}

function unitHtml(card, info) {
  return miniUnit(card, {
    target: info.targets.has(card.uid),
    assigned: info.split[card.uid] || 0,
    develop: info.develop[card.uid] || null,
    developResource: info.developResource[card.uid] || null,
    bank: info.bank[card.uid] || null,
    canAttack: Boolean(info.attacks[card.uid]),
    selected: info.attacker === card.uid,
    attackTarget: info.attackTargets.has(card.uid),
  });
}

const place = (html, attrs) => `<div class="place" ${attrs}>${html}</div>`;

function tierLabel(tier, rules) {
  const r = rules[String(tier)] || {};
  const vp = r.vp ? t("ui.tiers.vp", { vp: r.vp }) : t("ui.tiers.no_vp");
  const dev = r.develop_cost ? ` · ↑${r.develop_cost}` : "";
  return `<span class="ring-label" data-label="${tier}">${t("ui.tiers.tier", { tier })} · ${vp}${dev}</span>`;
}

export function tableHtml(view, store) {
  const info = targetInfo(view, store);
  const n = view.players.length;
  const rules = view.players[view.you].tier_rules;
  const items = [];
  for (const p of view.players) {
    const angle = ANGLES[n][relativeSeat(view, p.seat)];
    for (const tier of [1, 2, 3]) {
      const cells = (p.tiers[String(tier)] || []).map((u) => (u ? unitHtml(u, info) : emptySlot()));
      if (tier === 1) p.tokens.forEach((u) => cells.push(unitHtml(u, info)));
      cells.forEach((html, i) => items.push(place(html, `data-ring="${tier}" data-angle="${angle}" data-i="${i}" data-n="${cells.length}"`)));
    }
  }
  view.tier4.forEach((u, i) =>
    items.push(place(u ? unitHtml(u, info) : emptySlot(), `data-ring="4" data-i="${i}" data-n="${view.tier4.length}"`)),
  );
  const rings = [1, 2, 3, 4].map((k) => `<div class="ring t${k}" data-ring-edge="${k}"></div>`).join("");
  return `
    <div class="table" data-table>
      ${rings}
      ${[1, 2, 3, 4].map((k) => tierLabel(k, rules)).join("")}
      ${items.join("")}
    </div>`;
}

const RAD = Math.PI / 180;
const apart = (rx, ry, a, b, cw, ch) =>
  Math.abs(rx * (Math.cos(a * RAD) - Math.cos(b * RAD))) >= cw || Math.abs(ry * (Math.sin(a * RAD) - Math.sin(b * RAD))) >= ch;

// Angles of n cards centred on `angle` along an (rx, ry) ellipse, each just clear of its neighbour.
// Index 0 is on the owner's left (the larger angle).
function arcAngles(angle, n, rx, ry, cw, ch) {
  const next = (from, dir) => {
    let a = from;
    for (let k = 0; k < 240 && !apart(rx, ry, from, a, cw, ch); k += 1) a += dir * 0.5;
    return a;
  };
  let up = [];
  let down = [];
  if (n % 2) up = [angle];
  else {
    let d = 0; // symmetric pair around the centre
    while (d < 120 && !apart(rx, ry, angle - d, angle + d, cw, ch)) d += 0.25;
    up = [angle + d];
    down = [angle - d];
  }
  while (up.length + down.length < n) {
    up.push(next(up[up.length - 1], 1));
    if (up.length + down.length < n) down.push(next(down.length ? down[down.length - 1] : up[0], -1));
  }
  return [...up.slice().reverse(), ...down].slice(0, n).sort((x, y) => y - x);
}

// Ring sizes and card positions for a table of half size (w, h) at card scale s.
// items: [{ring, angle, i, n}] -> {ok, pos: [[x, y]], edges: {k: [rx, ry]}, mids: {k: [rx, ry]}}
export function computeLayout(w, h, items, s) {
  const cw = UNIT_W * s + GAP;
  const ch = UNIT_H * s + GAP;
  const bandX = Math.max(cw + 4, (w - cw / 2) * 0.24);
  const bandY = Math.max(ch + 12 * s, (h - ch / 2) * 0.24);
  const mids = {};
  const edges = { 1: [w, h] };
  let mx = w - cw / 2 - 2;
  let my = h - ch / 2 - 2;
  for (const k of [1, 2, 3]) {
    mids[k] = [mx, my];
    edges[k + 1] = [mx - bandX / 2, my - bandY / 2];
    mx -= bandX;
    my -= bandY;
  }
  const [rx4, ry4] = edges[4];
  const arcs = {};
  const pos = items.map((it) => {
    if (it.ring === 4) {
      const perRow = Math.max(1, Math.floor((2 * rx4 * 0.92) / cw));
      const rows = Math.ceil(it.n / perRow);
      const row = Math.floor(it.i / perRow);
      const inRow = row < rows - 1 ? perRow : it.n - perRow * (rows - 1);
      return [(it.i - row * perRow - (inRow - 1) / 2) * cw, (row - (rows - 1) / 2) * ch + 8 * s];
    }
    const [rx, ry] = mids[it.ring];
    const key = `${it.ring}:${it.angle}:${it.n}`;
    if (!arcs[key]) arcs[key] = arcAngles(it.angle, it.n, rx, ry, cw, ch);
    const a = arcs[key][it.i] * RAD;
    return [rx * Math.cos(a), ry * Math.sin(a)];
  });
  // Valid when no two cards overlap and every card is on the table.
  const hw = (UNIT_W * s) / 2;
  const hh = (UNIT_H * s) / 2;
  let ok = rx4 > 0 && ry4 > 0;
  for (let i = 0; ok && i < pos.length; i += 1) {
    const [x, y] = pos[i];
    if (Math.abs(x) + hw > w || Math.abs(y) + hh > h) ok = false;
    for (let j = i + 1; ok && j < pos.length; j += 1) {
      if (Math.abs(x - pos[j][0]) < cw - 2 && Math.abs(y - pos[j][1]) < ch - 2) ok = false;
    }
  }
  return { ok, pos, edges, mids };
}

// Largest card scale (1 down to 0.6) at which everything fits.
export function fitLayout(w, h, items) {
  let layout = null;
  for (let s = 1; s >= 0.6; s -= 0.04) {
    layout = { ...computeLayout(w, h, items, s), scale: s };
    if (layout.ok) break;
  }
  return layout;
}

// Put every unit / empty spot on its ring. Call after render and on resize.
export function layoutTable(root) {
  const table = root.querySelector("[data-table]");
  if (!table) return;
  const w = table.clientWidth / 2;
  const h = table.clientHeight / 2;
  const places = [...table.querySelectorAll(".place")];
  const items = places.map((el) => ({
    ring: Number(el.dataset.ring), angle: Number(el.dataset.angle || 0), i: Number(el.dataset.i), n: Number(el.dataset.n),
  }));
  const { pos, edges, mids, scale } = fitLayout(w, h, items);
  table.style.setProperty("--unit-scale", scale.toFixed(2));
  places.forEach((el, i) => {
    el.style.left = `${w + pos[i][0]}px`;
    el.style.top = `${h + pos[i][1]}px`;
  });
  table.querySelectorAll("[data-ring-edge]").forEach((el) => {
    const [rx, ry] = edges[el.dataset.ringEdge];
    el.style.width = `${2 * rx}px`;
    el.style.height = `${2 * ry}px`;
  });
  table.querySelectorAll("[data-label]").forEach((el) => {
    const k = Number(el.dataset.label);
    const [x, y] = k === 4 ? [0, -edges[4][1] + 10] : [mids[k][0] * Math.cos((LABEL_ANGLE * Math.PI) / 180), mids[k][1] * Math.sin((LABEL_ANGLE * Math.PI) / 180)];
    el.style.left = `${w + x}px`;
    el.style.top = `${h + y}px`;
  });
}
