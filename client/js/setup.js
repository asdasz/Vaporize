// Temporary dev "lobby": start a hot-seat game for 2-4 players.
import { t } from "./i18n.js";

export function renderSetup(root, { onCreate }) {
  root.innerHTML = `
    <div class="setup">
      <h1>${t("ui.app.title")}</h1>
      <div class="label">${t("ui.setup.heading")}</div>
      <div class="buttons">
        ${[2, 3, 4].map((n) => `<button data-players="${n}">${t("ui.setup.players", { count: n })}</button>`).join("")}
      </div>
      <div class="muted">${t("ui.setup.hint")}</div>
      <div class="error muted" id="setup-error"></div>
    </div>`;
  root.onclick = async (event) => {
    const btn = event.target.closest("[data-players]");
    if (!btn) return;
    try {
      await onCreate(Number(btn.dataset.players));
    } catch (err) {
      root.querySelector("#setup-error").textContent = t("ui.setup.error");
    }
  };
  root.onchange = null;
}
