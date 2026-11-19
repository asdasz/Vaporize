// Temporary dev "lobby": pick a class for each seat, then start a hot-seat game for 2-4 players.
import { t } from "./i18n.js";

const SEATS = 4;
let chosen = null; // class id per seat, kept while the page is open

export async function renderSetup(root, { onCreate, loadClasses, noticeKey = null }) {
  let classes = ["mage"];
  try {
    classes = await loadClasses();
  } catch {
    /* older server: Mage only */
  }
  if (!chosen || chosen.some((c) => !classes.includes(c))) {
    chosen = Array.from({ length: SEATS }, (_, i) => classes[i % classes.length]); // alternate by default
  }
  const pickers = chosen
    .map(
      (cls, seat) => `
      <label class="seat-pick"><span class="dot" style="background:var(--seat-${seat})"></span>
        ${t("ui.setup.seat", { seat: seat + 1 })}
        <select data-seat="${seat}">${classes
          .map((c) => `<option value="${c}" ${c === cls ? "selected" : ""}>${t(`classes.${c}.name`)}</option>`)
          .join("")}</select></label>`,
    )
    .join("");
  root.innerHTML = `
    <div class="setup">
      <h1>${t("ui.app.title")}</h1>
      ${noticeKey ? `<div class="chip error" style="margin:10px 0">${t(noticeKey)}</div>` : ""}
      <div class="label">${t("ui.setup.heading")}</div>
      <div class="seat-picks">${pickers}</div>
      <div class="buttons">
        ${[2, 3, 4].map((n) => `<button data-players="${n}">${t("ui.setup.players", { count: n })}</button>`).join("")}
      </div>
      <div class="muted">${t("ui.setup.hint")}</div>
      <div class="error muted" id="setup-error"></div>
    </div>`;
  root.onclick = async (event) => {
    const btn = event.target.closest("[data-players]");
    if (!btn) return;
    const players = Number(btn.dataset.players);
    try {
      await onCreate(players, chosen.slice(0, players));
    } catch (err) {
      root.querySelector("#setup-error").textContent = t("ui.setup.error");
    }
  };
  root.onchange = (event) => {
    const select = event.target.closest("[data-seat]");
    if (select) chosen[Number(select.dataset.seat)] = select.value;
  };
}
