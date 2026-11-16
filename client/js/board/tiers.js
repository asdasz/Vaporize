// Tier table: one column per player, rows T4 (shared) -> T1. Card border = owner colour.
import { t } from "../i18n.js";
import { emptySlot, miniUnit } from "./card.js";
import { esc, seatColor } from "./util.js";

function rowLabel(tier, rules, extraClass = "") {
  const r = rules[String(tier)] || {};
  const vp = r.vp ? t("ui.tiers.vp", { vp: r.vp }) : t("ui.tiers.no_vp");
  const dev = r.develop_cost ? ` · ${t("ui.tiers.develop", { cost: r.develop_cost })}` : "";
  const shared = tier === 4 ? ` ${t("ui.tiers.shared")}` : "";
  return `<div class="row-label ${extraClass}"><b>${t("ui.tiers.tier", { tier })}</b>${shared}<br>${vp}${dev}</div>`;
}

function slots(row) {
  return row.map((card) => (card ? miniUnit(card) : emptySlot())).join("");
}

export function tierTable(view) {
  const n = view.players.length;
  const rules = view.players[view.you].tier_rules;
  const colClass = (p) => (p.seat === view.current ? "current-col" : "");
  const cols = `grid-template-columns: 96px repeat(${n}, minmax(0, 1fr));`;

  const header = view.players
    .map(
      (p) => `<div class="head ${colClass(p)}" style="color:${seatColor(p.seat)}">
        <span><span class="dot" style="background:${seatColor(p.seat)}"></span> ${esc(p.name)} · ${t(`classes.${p.class_id}.name`)}</span>
        <small>${t("ui.tiers.hand", { count: p.hand_count })} · ${t("ui.tiers.deck", { count: p.deck_count })} · ${t("ui.tiers.discard", { count: p.discard.length })}</small>
      </div>`,
    )
    .join("");

  const t4 = `
    ${rowLabel(4, rules, "t4")}
    <div class="cell t4" style="grid-column: span ${n}">
      ${slots(view.tier4)}
      <span class="label" style="color:var(--gold);align-self:center">${t("ui.tiers.slots_shared", { count: view.tier4.length })}</span>
    </div>`;

  const ownRows = [3, 2, 1]
    .map((tier) => {
      const cells = view.players
        .map((p) => {
          const tokens = tier === 1 ? p.tokens.map(miniUnit).join("") : "";
          return `<div class="cell ${colClass(p)}">${slots(p.tiers[String(tier)])}${tokens}</div>`;
        })
        .join("");
      return rowLabel(tier, rules) + cells;
    })
    .join("");

  return `<div class="tiers" style="${cols}"><div></div>${header}${t4}${ownRows}</div>`;
}
