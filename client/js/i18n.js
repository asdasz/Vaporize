// Translation lookup. Keys are "<namespace>.<path>", e.g. "ui.panel.end_turn", "cards.MAG-S01.name".
const NAMESPACES = ["ui", "cards", "classes", "keywords", "log", "error", "prompt"];
const FALLBACK_LANG = "en";

let dict = {};
let fallback = {};

async function fetchLocale(lang) {
  const out = {};
  await Promise.all(
    NAMESPACES.map(async (ns) => {
      const res = await fetch(`/locales/${lang}/${ns}.json`);
      out[ns] = res.ok ? await res.json() : {};
    }),
  );
  return out;
}

export async function loadLocale(lang = FALLBACK_LANG) {
  fallback = await fetchLocale(FALLBACK_LANG);
  dict = lang === FALLBACK_LANG ? fallback : await fetchLocale(lang);
  document.documentElement.lang = lang;
}

function lookup(obj, key) {
  return key.split(".").reduce((node, part) => (node && typeof node === "object" ? node[part] : undefined), obj);
}

export function raw(key) {
  const value = lookup(dict, key);
  return value !== undefined ? value : lookup(fallback, key);
}

export function t(key, params = {}) {
  const value = raw(key);
  if (typeof value !== "string") return key;
  return value.replace(/\{(\w+)\}/g, (match, name) => (name in params ? String(params[name]) : match));
}
