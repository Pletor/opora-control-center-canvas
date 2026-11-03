// Tlačítka webu `settings.buttons` a jejich vlastní CSS `settings.customCss.button` (kontrakt Správy webu §0 bod 3,
// §2; backend `backend/project/site_admin/buttons.py`). Stav kromě `default` ukládá jen rozdíl proti `default`;
// server rozdíl spočítá sám, frontend proto může poslat i zděděnou hodnotu. Prázdné pole = klíč pryč.

export type StateName = "default" | "hover" | "active" | "focusVisible" | "disabled";
export const STATES: { id: StateName; label: string }[] = [
  { id: "default", label: "Tlačítko" }, { id: "hover", label: "Hover" }, { id: "active", label: "Active" },
  { id: "focusVisible", label: "Focus" }, { id: "disabled", label: "Disabled" },
];
export type Preset = "solid" | "outline" | "ghost" | "link";
export const PRESETS: Preset[] = ["solid", "outline", "ghost", "link"];
export type Gradient = { gradient: { angle: number; stops: { color: string; position: number }[] } };
export type Background = string | Gradient;
type Sub = Record<string, string | number | string[]>;
export type ButtonState = {
  background?: Background; color?: string; radius?: string; shadow?: string; width?: "auto" | "full";
  border?: Sub; font?: Sub; transition?: Sub; outline?: Sub;
};
export type Variant = { label?: string; preset: Preset; states: Partial<Record<StateName, ButtonState>> };
export type SizeName = "sm" | "md" | "lg";
export const SIZES: SizeName[] = ["sm", "md", "lg"];
export type Size = { paddingX: string; paddingY: string; minHeight: string; fontSize: string };
export type Buttons = { sizes: Record<SizeName, Size>; variants: Record<string, Variant> };

const DEFAULT_SIZES: Record<SizeName, Size> = {
  sm: { paddingX: "0.875rem", paddingY: "0.375rem", minHeight: "32px", fontSize: "0.875rem" },
  md: { paddingX: "1.5rem", paddingY: "0.625rem", minHeight: "44px", fontSize: "1rem" },
  lg: { paddingX: "2rem", paddingY: "0.875rem", minHeight: "52px", fontSize: "1.125rem" },
};
const MOTION = { properties: ["background-color", "color", "border-color", "box-shadow"], duration: "150ms", easing: "ease" };
const ring = (color: string) => ({ outline: { width: "2px", style: "solid", color, offset: "2px" } });

/** Předvolby pro prázdný dokument (`variants: {}`): pět variant z kontraktu s literálními barvami, které projdou
 *  kontrastem; člověk je pak přepíše na tokeny. */
export const PRESET_VARIANTS: Record<string, Variant> = {
  primary: { label: "Primary", preset: "solid", states: {
    default: { background: "#1c9749", color: "#ffffff", radius: "md", transition: MOTION },
    hover: { background: "#157a3a" }, active: { background: "#0f5c2b" }, focusVisible: ring("#0f5c2b"),
    disabled: { background: "#c9d1cc", color: "#4b5563" } } },
  secondary: { label: "Secondary", preset: "solid", states: {
    default: { background: "#e6efe8", color: "#14361f", radius: "md", transition: MOTION },
    hover: { background: "#d3e4d8" }, focusVisible: ring("#14361f"), disabled: { background: "#eef1ef", color: "#6b7280" } } },
  outline: { label: "Outline", preset: "outline", states: {
    default: { background: "transparent", color: "#14361f", radius: "md", border: { width: "2px", style: "solid", color: "#1c9749" }, transition: MOTION },
    hover: { background: "#e6efe8" }, focusVisible: ring("#14361f"), disabled: { color: "#6b7280", border: { color: "#9ca3af" } } } },
  ghost: { label: "Ghost", preset: "ghost", states: {
    default: { background: "transparent", color: "#14361f", radius: "md", transition: MOTION },
    hover: { background: "#eef4f0" }, focusVisible: ring("#14361f"), disabled: { color: "#6b7280" } } },
  link: { label: "Link", preset: "link", states: {
    default: { background: "transparent", color: "#1c5fb8", radius: "none", transition: MOTION },
    hover: { color: "#123f7a" }, focusVisible: ring("#123f7a"), disabled: { color: "#6b7280" } } },
};

export function readButtons(settings: Record<string, unknown>): Buttons {
  const raw = (settings.buttons ?? {}) as Partial<Buttons>;
  return { sizes: { ...DEFAULT_SIZES, ...raw.sizes }, variants: { ...raw.variants } };
}
export function readCustomCss(settings: Record<string, unknown>): Record<string, string> {
  return { ...((settings.customCss as { button?: Record<string, string> } | undefined)?.button) };
}

/** Proč jméno varianty nejde (prázdné = jde): a-z0-9-, ne velikost, ne obsazené. */
export function slugProblem(slug: string, buttons: Buttons): string {
  if (!/^[a-z][a-z0-9-]{0,31}$/.test(slug)) return "Jméno je a-z, 0-9 a pomlčka, začíná písmenem.";
  if ((SIZES as string[]).includes(slug)) return "sm, md a lg jsou velikosti.";
  if (buttons.variants[slug]) return "Varianta už existuje.";
  if (Object.keys(buttons.variants).length >= 16) return "Nejvýš 16 variant.";
  return "";
}

/** Nová varianta: předvolba stejného jména, jinak kopie primary s vlastním jménem. */
export function addVariant(buttons: Buttons, slug: string): Buttons {
  const base = structuredClone(PRESET_VARIANTS[slug] ?? { ...PRESET_VARIANTS.primary, label: slug });
  return { ...buttons, variants: { ...buttons.variants, [slug]: base } };
}
export function removeVariant(buttons: Buttons, slug: string): Buttons {
  const { [slug]: _gone, ...variants } = buttons.variants;
  return { ...buttons, variants };
}
export const withVariant = (buttons: Buttons, slug: string, variant: Variant): Buttons =>
  ({ ...buttons, variants: { ...buttons.variants, [slug]: variant } });
export const withSize = (buttons: Buttons, size: SizeName, key: keyof Size, value: string): Buttons =>
  ({ ...buttons, sizes: { ...buttons.sizes, [size]: { ...buttons.sizes[size], [key]: value.trim() || DEFAULT_SIZES[size][key] } } });

const empty = (value: unknown) => value === undefined || value === null || value === "" || (Array.isArray(value) && !value.length);

/** Varianta po změně jednoho pole stavu; prázdná hodnota pole odebere. */
export function withStateKey<K extends keyof ButtonState>(variant: Variant, state: StateName, key: K, value: ButtonState[K] | undefined): Variant {
  const next: ButtonState = { ...variant.states[state] };
  if (empty(value)) delete next[key]; else next[key] = value;
  return { ...variant, states: { ...variant.states, [state]: next } };
}

/** Varianta po změně pole vnořeného objektu (rámeček, font, přechod, focus ring); prázdný objekt zmizí. */
export function withNestedKey(variant: Variant, state: StateName, key: "border" | "font" | "transition" | "outline", field: string, value: string | number | string[] | undefined): Variant {
  const sub: Sub = { ...variant.states[state]?.[key] };
  if (empty(value)) delete sub[field]; else sub[field] = value as string;
  return withStateKey(variant, state, key, Object.keys(sub).length ? sub : undefined);
}

/** Co ve stavu platí: `default` a přes něj rozdíl stavu (vnořené objekty po polích, jako server). */
export function effective(variant: Variant, state: StateName): ButtonState {
  const base = variant.states.default ?? {};
  if (state === "default") return base;
  const own = variant.states[state] ?? {};
  const out: ButtonState = { ...base, ...own };
  for (const key of ["border", "font", "transition"] as const) if (base[key] && own[key]) out[key] = { ...base[key], ...own[key] };
  return out;
}

/** Poznámky serveru (kontrast, focus ring, chyby vlastního CSS) k jedné variantě. */
export function variantNotes(notes: string[], slug: string): string[] {
  return notes.filter((note) => note.startsWith(`Tlačítko ${slug} `) || note.startsWith(`Tlačítko ${slug}:`) || note.startsWith(`Tlačítka `) || note.includes(`customCss.button.${slug}`)
    || note.includes(`buttons.variants.${slug}.`));
}
