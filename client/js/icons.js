// Inline SVG icons (no external icon font). Elements are always shown as icons, never colours.
const PATHS = {
  fire: "M12 3c1 4 6 6 6 11a6 6 0 0 1-12 0c0-3 2-5 3-6 0 2 1 3 2 3 0-3 0-5 1-8z",
  water: "M12 3s-7 8-7 12a7 7 0 0 0 14 0c0-4-7-12-7-12z",
  wind: "M3 8h11a3 3 0 1 0-3-3M3 12h16a3 3 0 1 1-3 3M3 16h7",
  lightning: "M13 3 4 14h7l-1 7 9-11h-7z",
  shadow: "M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z",
  attack: "M20 4 9 15M14 4h6v6M6 13l5 5M4 15l5 5M7 17l-3 3",
  health: "M12 20s-8-5-8-11a4.5 4.5 0 0 1 8-2.5A4.5 4.5 0 0 1 20 9c0 6-8 11-8 11z",
  shield: "M12 3l8 3v6c0 5-4 8-8 9-4-1-8-4-8-9V6z",
  stun: "M12 3a9 9 0 1 0 .01 0M5.6 5.6l12.8 12.8",
  freeze: "M12 3v18M4.2 7.5l15.6 9M19.8 7.5l-15.6 9",
  star: "M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z",
  refresh: "M20 11a8 8 0 0 0-14.9-3M4 4v4h4M4 13a8 8 0 0 0 14.9 3M20 20v-4h-4",
  cards: "M8 4h11v15H8zM5 7v13h11",
  arrowUp: "M12 19V5M5 12l7-7 7 7",
  undo: "M9 14 4 9l5-5M4 9h11a5 5 0 0 1 0 10h-3",
  cancel: "M6 6l12 12M18 6 6 18",
  check: "M5 12l5 5L20 7",
  trash: "M4 7h16M10 11v6M14 11v6M5 7l1 13h12l1-13M9 7V4h6v3",
};

export function icon(name, title = "") {
  const d = PATHS[name] || "";
  const label = title ? `<title>${title}</title>` : "";
  return `<svg class="ic" viewBox="0 0 24 24" aria-hidden="${title ? "false" : "true"}">${label}<path d="${d}"/></svg>`;
}
