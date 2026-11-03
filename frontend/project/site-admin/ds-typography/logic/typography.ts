// Typografie design systému `design.tokens.type = {fonts, families, groups}` v gramatice formátu: rodiny jsou
// stacky písma (`--font-<klíč>`), fonty soubory v `site/fonts/` s `@font-face`, skupiny drží styly (třída `.<styl>`).
// Styly mají vlastní jmenný prostor, oddělený od tokenů.
import type { FontFile, TypeFamily, TypeGroup, TypeStyle } from "@/project/site-admin/logic/site-document";
import { cssLength, cssLineHeight } from "@/project/site-admin/ds-preview/logic/tokens-scope";

export const FONT_ACCEPT = ".woff2,.woff,.ttf,.otf";
export const MAX_FAMILIES = 12, MAX_GROUPS = 12, MAX_STYLES = 80;
const WEIGHTS: [RegExp, number][] = [[/thin|hairline/, 100], [/extra-?light|ultra-?light/, 200], [/light/, 300], [/medium/, 500],
  [/semi-?bold|demi-?bold/, 600], [/extra-?bold|ultra-?bold/, 800], [/bold/, 700], [/black|heavy/, 900]];

/** Záznam `type.fonts` z nahraného souboru: rodina z první části jména, váha a řez z přípony jména. */
export function fontFromUpload(fileName: string, path: string): FontFile {
  const stem = fileName.replace(/\.[^.]+$/, "");
  const lower = stem.toLowerCase();
  const family = stem.split(/[-_]/)[0].replace(/([a-z])([A-Z])/g, "$1 $2").trim() || "Font";
  const variable = /variable|\bvf\b|\[/.test(lower);
  const weight = variable ? "100 900" : String(WEIGHTS.find(([pattern]) => pattern.test(lower))?.[1] ?? 400);
  return { family, file: path, weight, style: /italic|oblique/.test(lower) ? "italic" : "normal" };
}

export const totalStyles = (type: TypeFamily) => type.groups.reduce((sum, group) => sum + group.styles.length, 0);
export const styleNames = (type: TypeFamily) => type.groups.flatMap((group) => group.styles.map((style) => style.name));

/** Přejmenuje nebo upraví rodinu; odkazy skupin a stylů na starý klíč se přepíšou. */
export function setFamily(type: TypeFamily, key: string, next: string, stack: string): TypeFamily {
  const families = Object.fromEntries(Object.entries(type.families).map(([name, value]) => name === key ? [next, stack] : [name, value]));
  const swap = <T extends { family?: string }>(item: T): T => item.family === key ? { ...item, family: next } : item;
  return { ...type, families, groups: type.groups.map((group) => ({ ...swap(group), styles: group.styles.map(swap) })) };
}

export function addFamily(type: TypeFamily, key: string, stack: string): TypeFamily {
  if (key in type.families || Object.keys(type.families).length >= MAX_FAMILIES) return type;
  return { ...type, families: { ...type.families, [key]: stack } };
}

/** Odebere rodinu; skupiny a styly, které ji používaly, zůstanou bez rodiny (dědí písmo stránky). */
export function removeFamily(type: TypeFamily, key: string): TypeFamily {
  const { [key]: _gone, ...families } = type.families;
  const drop = <T extends { family?: string }>(item: T): T => { if (item.family !== key) return item; const { family: _f, ...rest } = item; return rest as T; };
  return { ...type, families, groups: type.groups.map((group) => ({ ...drop(group), styles: group.styles.map(drop) })) };
}

export const updateFont = (type: TypeFamily, index: number, font: FontFile): TypeFamily => ({ ...type, fonts: type.fonts.map((item, at) => at === index ? font : item) });
export const removeFont = (type: TypeFamily, index: number): TypeFamily => ({ ...type, fonts: type.fonts.filter((_, at) => at !== index) });

export function addGroup(type: TypeFamily, name: string): TypeFamily {
  if (type.groups.length >= MAX_GROUPS) return type;
  const family = Object.keys(type.families)[0];
  return { ...type, groups: [...type.groups, { name, ...(family ? { family } : {}), styles: [] }] };
}
export const updateGroup = (type: TypeFamily, index: number, group: TypeGroup): TypeFamily => ({ ...type, groups: type.groups.map((item, at) => at === index ? group : item) });
export const removeGroup = (type: TypeFamily, index: number): TypeFamily => ({ ...type, groups: type.groups.filter((_, at) => at !== index) });

/** Nový styl ve skupině s volným jménem a rozumným výchozím tvarem (16/24/400). */
export function addStyle(type: TypeFamily, index: number, base = "style"): TypeFamily {
  if (totalStyles(type) >= MAX_STYLES) return type;
  const taken = styleNames(type);
  let name = base;
  for (let at = 2; taken.includes(name); at++) name = `${base}-${at}`;
  const style: TypeStyle = { name, fontSize: "16px", lineHeight: 1.5, fontWeight: 400, sample: "Příliš žluťoučký kůň úpěl ďábelské ódy" };
  return updateGroup(type, index, { ...type.groups[index], styles: [...type.groups[index].styles, style] });
}

/** Inline styl živé ukázky z rozepsaných hodnot: platí hned, ještě před uložením a novým `tokens.css`. */
export function sampleCss(style: TypeStyle, group: TypeGroup): Record<string, string> {
  const family = style.family || group.family;
  const out: Record<string, string | undefined> = {
    fontFamily: family ? `var(--font-${family.replace(/\./g, "\\.")})` : undefined,
    fontSize: cssLength(style.fontSize), lineHeight: cssLineHeight(style.lineHeight),
    fontWeight: style.fontWeight === undefined ? undefined : String(style.fontWeight),
    letterSpacing: cssLength(style.letterSpacing), fontStyle: style.fontStyle || undefined,
  };
  return Object.fromEntries(Object.entries(out).filter((entry): entry is [string, string] => entry[1] !== undefined));
}
