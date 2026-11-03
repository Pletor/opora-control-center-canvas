// Barvy design systému: aliasy `{token}`, skupiny podle kmene jména, dvojice pro kontrast a úpravy seznamu.
// Pravidla aliasů jsou stejná jako v serveru (`tokens.py`): bez cyklu, bez chybějícího cíle, hloubka nejvýš 16.
import { themedValue, type ColorFamily, type Token } from "@/project/site-admin/logic/site-document";
import { contrastLevel, contrastRatio, type ContrastLevel } from "./color-contrast";

export const ALIAS = /^\{([A-Za-z0-9][A-Za-z0-9_.-]{0,63})\}$/;
const MAX_DEPTH = 16;

export const aliasTarget = (raw: string) => raw.match(ALIAS)?.[1] ?? null;

/** Skutečná barva tokenu v tématu po rozbalení aliasů; `{error}`, když alias nikam nevede. */
export function resolveColor(tokens: readonly Token[], name: string, theme: string, first: string): { value: string } | { error: string } {
  const seen: string[] = [];
  let current = name;
  for (;;) {
    const token = tokens.find((item) => item.name === current);
    if (!token) return { error: `alias na neexistující ${current}` };
    const raw = themedValue(token.value, theme, first);
    const target = aliasTarget(raw);
    if (!target) return raw ? { value: raw } : { error: "bez hodnoty" };
    seen.push(current);
    if (seen.includes(target)) return { error: "alias v cyklu" };
    if (seen.length > MAX_DEPTH) return { error: "alias hlubší než 16" };
    current = target;
  }
}

/** Kmen jména pro skupinu: `bg-100` → `bg`, `on-ember` → `ember` (text patří ke své výplni). */
export function colorStem(name: string): string {
  return name.replace(/^on-/, "").split(/[-.]/)[0];
}

/** Tokeny po skupinách v pořadí prvního výskytu kmene; index ukazuje do původního seznamu. */
export function colorGroups(tokens: readonly Token[]): { stem: string; items: { token: Token; index: number }[] }[] {
  const groups = new Map<string, { token: Token; index: number }[]>();
  tokens.forEach((token, index) => {
    const stem = colorStem(token.name);
    groups.set(stem, [...(groups.get(stem) ?? []), { token, index }]);
  });
  return [...groups].map(([stem, items]) => ({ stem, items }));
}

/** S čím se barva čte: `on-x` ↔ `x`, `ink*` na `surface`, `surface*`/`bg*` pod `ink`, jinak na `surface`. */
export function contrastPair(name: string, names: readonly string[]): string | null {
  const has = (candidate: string) => candidate !== name && names.includes(candidate) ? candidate : null;
  if (name.startsWith("on-")) return has(name.slice(3));
  if (has("on-" + name)) return "on-" + name;
  if (/^(surface|bg)/.test(name)) return has("ink");
  return has("surface");
}

export type ContrastResult = { pair: string; ratio: number; level: ContrastLevel } | null;

/** Kontrast tokenu proti jeho dvojici v tématu; `null`, když dvojice chybí nebo barvu převést neumíme. */
export function tokenContrast(family: ColorFamily, name: string, theme: string): ContrastResult {
  const first = family.themes[0]?.id ?? theme;
  const pair = contrastPair(name, family.tokens.map((token) => token.name));
  if (!pair) return null;
  const a = resolveColor(family.tokens, name, theme, first), b = resolveColor(family.tokens, pair, theme, first);
  if (!("value" in a) || !("value" in b)) return null;
  const ratio = contrastRatio(a.value, b.value);
  return ratio === null ? null : { pair, ratio, level: contrastLevel(ratio) };
}

/** Přejmenování tokenu včetně aliasů, které na něj míří (v každém tématu). */
export function renameColor(tokens: readonly Token[], index: number, name: string): Token[] {
  const old = tokens[index].name;
  const swap = (raw: string) => aliasTarget(raw) === old ? `{${name}}` : raw;
  return tokens.map((token, at) => ({
    ...token, name: at === index ? name : token.name,
    value: typeof token.value === "string" ? swap(token.value) : Object.fromEntries(Object.entries(token.value).map(([id, raw]) => [id, swap(raw)])),
  }));
}

export const replaceToken = (tokens: readonly Token[], index: number, token: Token) => tokens.map((item, at) => at === index ? token : item);
export const removeToken = (tokens: readonly Token[], index: number) => tokens.filter((_, at) => at !== index);
