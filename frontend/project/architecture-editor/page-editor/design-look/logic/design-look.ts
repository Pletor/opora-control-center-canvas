// Přepínač Layout | Design vrstvy 1 a pruh Design webu (docs/navrhy/2026-11-10-platno-2.md, Verze 6): stav v adrese
// (`look=design`, výchozí Layout) a výtah z tokenů Design systému projektu pro pruh nad mřížkou (barevné vzorky, písma,
// ukázka tlačítka). Bez Reactu, test vedle.
import type { DesignTokens, TokenFamily } from "@/project/site-admin/logic/site-document";
import { themedValue } from "@/project/site-admin/logic/site-document";

export type Look = "layout" | "design";
export type Swatch = { name: string; color: string };
export type FontSample = { name: string; stack: string };

const ALIAS = /^\{([A-Za-z0-9][A-Za-z0-9_.-]{0,63})\}$/;
const SWATCHES = 12, FONTS = 4;

export const lookOf = (search: string): Look => (new URLSearchParams(search).get("look") === "design" ? "design" : "layout");

/** Dotaz adresy s pohledem Design, nebo bez parametru (výchozí Layout). */
export function withLookParam(search: string, look: Look): string {
  const params = new URLSearchParams(search);
  if (look === "design") params.set("look", "design"); else params.delete("look");
  return params.toString();
}

/** Barvy v prvním tématu, aliasy rozbalené (nejvýš 16 kroků); nerozbalitelný alias se vynechá. */
export function designSwatches(tokens: DesignTokens): Swatch[] {
  const first = tokens.color.themes[0]?.id ?? "light";
  const byName = new Map(tokens.color.tokens.map((token) => [token.name, themedValue(token.value, first, first)]));
  const resolve = (value: string | undefined, depth = 0): string | null => {
    const alias = value?.match(ALIAS);
    if (!alias) return value || null;
    return depth < 16 ? resolve(byName.get(alias[1]), depth + 1) : null;
  };
  return tokens.color.tokens.flatMap((token) => { const color = resolve(byName.get(token.name)); return color ? [{ name: token.name, color }] : []; }).slice(0, SWATCHES);
}

export const designFonts = (tokens: DesignTokens): FontSample[] =>
  Object.entries(tokens.type.families).map(([name, stack]) => ({ name, stack })).slice(0, FONTS);

/** Ukázka tlačítka z tokenů: rodina `button` (`button-bg`, `button-text`, `button-radius`, ze skenu), jinak barva
 * `primary`/`accent`/`brand` (nebo první barva) a zaoblení s „button“ v názvu (nebo první). */
export function designButton(tokens: DesignTokens): { background: string; color: string; radius: string; font: string } | null {
  const swatches = designSwatches(tokens);
  const own = (name: string) => { const value = (tokens.button as TokenFamily | undefined)?.tokens.find((token) => token.name === name)?.value; return typeof value === "string" ? value : null; };
  const font = designFonts(tokens)[0]?.stack ?? "inherit";
  const bg = own("button-bg");
  if (bg && !ALIAS.test(bg)) return { background: bg, color: own("button-text") ?? "#fff", radius: own("button-radius") ?? "6px", font };
  const color = ["primary", "accent", "brand"].map((name) => swatches.find((swatch) => swatch.name.toLowerCase().includes(name))).find(Boolean) ?? swatches[0];
  if (!color) return null;
  const radii = tokens.radius?.tokens ?? [];
  const radius = radii.find((token) => token.name.toLowerCase().includes("button")) ?? radii[0];
  return { background: color.color, color: "#fff", radius: typeof radius?.value === "string" ? radius.value : "6px", font };
}
