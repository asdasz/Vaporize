// Game log (newest first), under the private markets. Can be collapsed.
import { t } from "../i18n.js";
import { esc, eventText } from "./util.js";

export function logBox(view, store) {
  const items = store.logOpen ? [...view.log].reverse().map((e) => `<li>${esc(eventText(view, e))}</li>`).join("") : "";
  return `
    <div class="box log-box">
      <div class="market-head">
        <h3>${t("ui.side.log")}</h3>
        <button class="mini-link" data-action="toggle-log">${t(store.logOpen ? "ui.side.hide" : "ui.side.show")}</button>
      </div>
      ${store.logOpen ? `<ul class="list log">${items}</ul>` : ""}
    </div>`;
}
