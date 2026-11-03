// Spacing, Corner radius a Shadows: rodina `{note?, tokens: [{name, value, usage?}]}`. Spacing a radius mají délku
// (číslo = px), stín řetězec `box-shadow` nebo mapu per téma jako barvy. Ukázka bere hodnotu z rozepsaného dokumentu,
// takže se mění hned při psaní, ještě před uložením.
import { themedValue, type ScaleKind, type Token, type TokenFamily } from "@/project/site-admin/logic/site-document";
import { cssLength } from "@/project/site-admin/ds-preview/logic/tokens-scope";

export const SCALE_LIMIT = 60;
export const SCALE_BASE: Record<ScaleKind, { name: string; value: string }> = {
  spacing: { name: "space-1", value: "4px" },
  radius: { name: "radius-sm", value: "4px" },
  shadow: { name: "shadow-sm", value: "0 1px 2px rgba(0, 0, 0, 0.12)" },
};

/** Rodina vždy jako objekt; chybějící rodina je prázdná. */
export const scaleFamily = (family: TokenFamily | undefined): TokenFamily => family ?? { tokens: [] };

/** Poznámka rodiny; prázdná se z dokumentu vypustí. */
export function withNote(family: TokenFamily, note: string): TokenFamily {
  const { note: _old, ...rest } = family;
  return note ? { ...rest, note } : rest;
}

export function addScaleToken(family: TokenFamily, kind: ScaleKind, name: string): TokenFamily {
  if (family.tokens.length >= SCALE_LIMIT) return family;
  const last = family.tokens.at(-1);
  const value = last && typeof last.value === "string" ? last.value : SCALE_BASE[kind].value;
  return { ...family, tokens: [...family.tokens, { name, value }] };
}

export const updateScaleToken = (family: TokenFamily, index: number, token: Token): TokenFamily =>
  ({ ...family, tokens: family.tokens.map((item, at) => at === index ? token : item) });
export const removeScaleToken = (family: TokenFamily, index: number): TokenFamily =>
  ({ ...family, tokens: family.tokens.filter((_, at) => at !== index) });

/** Styl ukázky: pruh šířky mezery, čtverec se zaoblením, nebo karta se stínem v daném tématu. */
export function scaleSwatch(kind: ScaleKind, token: Token, theme: string, first: string): Record<string, string> {
  const raw = themedValue(token.value, theme, first);
  if (kind === "spacing") return { width: `min(${cssLength(raw) ?? "0"}, 100%)` };
  if (kind === "radius") return { borderRadius: cssLength(raw) ?? "0" };
  return { boxShadow: raw || "none" };
}
