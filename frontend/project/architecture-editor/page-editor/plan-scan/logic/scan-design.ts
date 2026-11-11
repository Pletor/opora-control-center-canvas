// Design ze skenu webu → Design systém projektu (docs/navrhy/2026-11-10-platno-2.md, Verze 6): tokeny návrhu
// (`design.tokens` Správy webu) se slijí do uložených podle jména tokenu v rodině, písma podle klíče rodiny písem a styly
// podle jména skupiny a stylu. Nic se nemaže; témata a soubory písem zůstávají uložené. Hodnota barvy, která je
// uložená po tématech, dostane novou hodnotu jen v prvním tématu (tmavé téma se nezploští). Seznam změn staré → nové
// ukáže panel skenu před zápisem. Bez Reactu, test vedle.
import { withThemeValue, type DesignTokens, type ThemedValue, type Token, type TokenFamily, type TypeGroup, type TypeStyle } from "@/project/site-admin/logic/site-document";

export type TokenChange = { path: string; before: string | null; after: string };
type Merged = { tokens: DesignTokens; changes: TokenChange[] };

const record = (value: unknown): Record<string, unknown> => (value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {});
const list = (value: unknown): Record<string, unknown>[] => (Array.isArray(value) ? value.map(record) : []);
const shown = (value: unknown) => (typeof value === "string" ? value : JSON.stringify(value));
const themed = (value: unknown): value is ThemedValue => typeof value === "string" || (!!value && typeof value === "object" && !Array.isArray(value));
const FIXED = new Set(["color", "type", "version"]);

/** Tokeny rodiny podle jména: přepíše hodnotu stejně pojmenovaného, nový přidá na konec. */
function mergeTokens(family: string, current: readonly Token[], proposed: unknown, changes: TokenChange[], adapt = (_old: ThemedValue, next: ThemedValue) => next): Token[] {
  const tokens = [...current];
  for (const item of list(proposed)) {
    if (typeof item.name !== "string" || !item.name || !themed(item.value)) continue;
    const index = tokens.findIndex((token) => token.name === item.name);
    const value = index >= 0 ? adapt(tokens[index].value, item.value) : item.value;
    if (index >= 0 && shown(tokens[index].value) === shown(value)) continue;
    changes.push({ path: `${family}.${item.name}`, before: index >= 0 ? shown(tokens[index].value) : null, after: shown(value) });
    if (index >= 0) tokens[index] = { ...tokens[index], value }; else tokens.push({ name: item.name, value, ...(typeof item.usage === "string" ? { usage: item.usage } : {}) });
  }
  return tokens;
}

function mergeStyles(group: TypeGroup | undefined, proposed: Record<string, unknown>, changes: TokenChange[]): TypeGroup {
  const name = String(proposed.name);
  const styles: TypeStyle[] = [...(group?.styles ?? [])];
  for (const item of list(proposed.styles)) {
    if (typeof item.name !== "string" || typeof item.fontSize !== "string") continue;
    const style = item as unknown as TypeStyle;
    const index = styles.findIndex((entry) => entry.name === style.name);
    if (index >= 0 && shown(styles[index]) === shown({ ...styles[index], ...style })) continue;
    changes.push({ path: `type.${name}.${style.name}`, before: index >= 0 ? styles[index].fontSize : null, after: style.fontSize });
    if (index >= 0) styles[index] = { ...styles[index], ...style }; else styles.push(style);
  }
  return { ...(group ?? { name }), styles };
}

export function mergeDesignTokens(current: DesignTokens, proposed: Record<string, unknown> | null): Merged {
  const changes: TokenChange[] = [];
  if (!proposed) return { tokens: current, changes };
  const first = current.color.themes[0]?.id ?? "light";
  const color = record(proposed.color);
  const colors = mergeTokens("color", current.color.tokens, color.tokens, changes,
    (old, next) => (typeof old === "string" || typeof next !== "string" ? next : withThemeValue(old, first, next, current.color.themes)));
  const type = record(proposed.type);
  const families = { ...current.type.families };
  for (const [key, stack] of Object.entries(record(type.families))) {
    if (typeof stack !== "string" || families[key] === stack) continue;
    changes.push({ path: `type.families.${key}`, before: families[key] ?? null, after: stack });
    families[key] = stack;
  }
  const groups = [...current.type.groups];
  for (const item of list(type.groups)) {
    if (typeof item.name !== "string" || !item.name) continue;
    const index = groups.findIndex((group) => group.name === item.name), before = changes.length;
    const merged = mergeStyles(groups[index], item, changes);
    if (changes.length === before) continue;
    if (index >= 0) groups[index] = merged; else groups.push(merged);
  }
  const tokens: DesignTokens = { ...current, color: { ...current.color, tokens: colors }, type: { ...current.type, families, groups } };
  for (const [key, value] of Object.entries(proposed)) {
    if (FIXED.has(key) || !Array.isArray(record(value).tokens)) continue;
    const family = (current[key] as TokenFamily | undefined) ?? { tokens: [] };
    tokens[key] = { ...family, tokens: mergeTokens(key, family.tokens, record(value).tokens, changes) };
  }
  return changes.length ? { tokens, changes } : { tokens: current, changes };
}
