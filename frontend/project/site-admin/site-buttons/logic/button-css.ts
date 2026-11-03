// CSS náhledu z rozepsaných tlačítek: stejné komponentní tokeny `--btn-*` jako server (`buttons.py::css`), jen pod
// `.ds-web` a s hodnotami z formuláře, takže neuložená změna je vidět hned. Základ `.ds-btn` (padding, rámeček přes
// proměnné) dává uložený `components.css`; tady jsou velikosti, varianty a stavy. Náhled navíc umí stav vynutit
// třídou `ds-btn--is-<stav>`, aby šlo vidět Hover nebo Focus bez myši.
import { cssValue } from "@/project/site-admin/site-fields/logic/field-values";
import { backgroundCss } from "./button-gradient";
import { SIZES, STATES, type ButtonState, type Buttons, type StateName } from "./button-model";

export const RADIUS: Record<string, string> = { none: "0", sm: "4px", md: "8px", lg: "16px", pill: "999px" };
const ROOT = ".ds-web";
const PSEUDO: Record<StateName, string[]> = {
  default: [""], hover: [':hover:not(:disabled):not([aria-disabled="true"])'], active: [':active:not(:disabled):not([aria-disabled="true"])'],
  focusVisible: [":focus-visible"], disabled: [":disabled", '[aria-disabled="true"]'],
};
const FONT: Record<string, string> = { weight: "--btn-font-weight", letterSpacing: "--btn-letter-spacing", transform: "--btn-text-transform" };

const line = (name: string, value: string | null) => value ? [`${name}: ${value};`] : [];

/** Deklarace `--btn-*` jednoho stavu. */
export function stateLines(state: ButtonState): string[] {
  const out: string[] = [...line("--btn-bg", backgroundCss(state.background)), ...line("--btn-color", cssValue(state.color)),
    ...line("--btn-shadow", cssValue(state.shadow)), ...line("--btn-radius", cssValue(RADIUS[state.radius ?? ""] ?? state.radius))];
  if (state.width) out.push(`--btn-width: ${state.width === "full" ? "100%" : "auto"};`);
  for (const [key, prefix] of [["border", "--btn-border"], ["outline", "--btn-ring"]] as const)
    for (const [field, value] of Object.entries(state[key] ?? {})) out.push(...line(`${prefix}-${field}`, cssValue(value)));
  for (const [field, value] of Object.entries(state.font ?? {})) {
    if (field === "family") out.push(...line("--btn-font-family", /^[A-Za-z0-9_-]+$/.test(String(value)) ? `var(--font-${value})` : null));
    else if (FONT[field]) out.push(...line(FONT[field], cssValue(value)));
  }
  if (state.transition) {
    const motion = state.transition as { properties?: string[]; duration?: string; easing?: string };
    const timing = `${cssValue(motion.duration) ?? "150ms"} ${cssValue(motion.easing) ?? "ease"}`;
    const properties = (motion.properties?.length ? motion.properties : ["background-color", "color", "border-color", "box-shadow"]).filter((item) => /^[a-z-]+$/.test(item));
    out.push(`--btn-transition: ${properties.map((item) => `${item} ${timing}`).join(", ")};`);
  }
  return out;
}

const block = (selectors: string[], lines: string[]) => lines.length ? [`${selectors.join(", ")} {`, ...lines.map((item) => "  " + item), "}"] : [];

/** Velikosti, varianty a stavy pod `.ds-web`, plus vynucené stavy pro náhled. */
export function buttonsCss(buttons: Buttons): string {
  const out = [
    ...block([`${ROOT} .ds-btn.ds-btn--is-focusVisible`], ["outline: var(--btn-ring-width) var(--btn-ring-style) var(--btn-ring-color);", "outline-offset: var(--btn-ring-offset);"]),
    ...SIZES.flatMap((size) => {
      const value = buttons.sizes[size];
      return block([`${ROOT} .ds-btn--${size}`], [...line("--btn-px", cssValue(value.paddingX)), ...line("--btn-py", cssValue(value.paddingY)),
        ...line("--btn-min-height", cssValue(value.minHeight)), ...line("--btn-font-size", cssValue(value.fontSize))]);
    }),
  ];
  for (const [slug, variant] of Object.entries(buttons.variants)) {
    if (!/^[a-z][a-z0-9-]{0,31}$/.test(slug)) continue;
    for (const { id } of STATES) {
      const state = variant.states[id];
      if (!state) continue;
      const selectors = PSEUDO[id].map((pseudo) => `${ROOT} .ds-btn--${slug}${pseudo}`);
      if (id !== "default") selectors.push(`${ROOT} .ds-btn--${slug}.ds-btn--is-${id}`);
      out.push(...block(selectors, stateLines(state)));
    }
  }
  return out.join("\n");
}
