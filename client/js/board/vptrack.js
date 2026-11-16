import { esc, seatColor } from "./util.js";

const GOAL = 30;

export function vpTrack(view) {
  const cells = [];
  for (let vp = 0; vp <= GOAL; vp += 1) {
    const here = view.players.filter((p) => Math.min(p.vp, GOAL) === vp);
    const pawns = here
      .map((p) => `<span class="pawn" style="background:${seatColor(p.seat)}" title="${esc(p.name)}: ${p.vp}"></span>`)
      .join("");
    cells.push(`
      <div class="vp-cell ${vp === GOAL ? "goal" : ""}">
        <span>${vp % 5 === 0 ? vp : ""}</span><span class="pawns">${pawns}</span>
      </div>`);
  }
  return `<div class="vp-track">${cells.join("")}</div>`;
}
