// Náhled Vzhledu z rozepsaného pohledu: stejná pravidla, jaká server skládá do `@layer base` v `components.css`
// (`compile.py::_base`), jen s hodnotami přímo z formuláře, takže se změna ukáže dřív než po Uložit. Selektory
// míří pod `.ds-web` (kořen náhledu je `body` webu), hodnoty prochází `cssValue` (alias → `var()`, nic, co by
// ukončilo deklaraci).
import { siteAdminUrls } from "@/project/site-admin/logic/site-admin-api";
import { cssLength, cssLineHeight } from "@/project/site-admin/ds-preview/logic/tokens-scope";
import { cssValue } from "@/project/site-admin/site-fields/logic/field-values";
import { LEVELS, type Appearance, type Leaf } from "./appearance";

const PATTERNS: Record<string, string[]> = {
  dots: ["radial-gradient(var(--pattern, currentColor) 1px, transparent 1.5px)"],
  grid: ["linear-gradient(var(--pattern, currentColor) 1px, transparent 1px)", "linear-gradient(90deg, var(--pattern, currentColor) 1px, transparent 1px)"],
  lines: ["linear-gradient(var(--pattern, currentColor) 1px, transparent 1px)"],
  diagonal: ["repeating-linear-gradient(45deg, var(--pattern, currentColor) 0 1px, transparent 1px 12px)"],
};

const length = (value: Leaf) => cssValue(cssLength(value ?? undefined));
const decl = (property: string, value: string | null | undefined) => value ? [`${property}: ${value};`] : [];
const rule = (selector: string, lines: string[]) => lines.length ? [`.ds-web${selector} {`, ...lines.map((line) => "  " + line), "}"] : [];

function background(appearance: Appearance, project: string): string[] {
  const { image, pattern, overlay } = appearance.background;
  const layers: [string, string, string, string][] = [];
  const opacity = typeof overlay.opacity === "number" ? overlay.opacity : 1;
  const tint = cssValue(overlay.color);
  if (tint) {
    const mix = `color-mix(in srgb, ${tint} ${opacity * 100}%, transparent)`;
    layers.push([`linear-gradient(${mix}, ${mix})`, "auto", "no-repeat", "0 0"]);
  }
  const scale = typeof pattern.scale === "number" ? pattern.scale : 1;
  for (const layer of PATTERNS[String(pattern.preset)] ?? []) layers.push([layer, `${16 * scale}px ${16 * scale}px`, "repeat", "0 0"]);
  const asset = typeof image.asset === "string" ? image.asset.match(/^assets\/([^/]+)\/(.+)$/) : null;
  if (asset) layers.push([`url("${siteAdminUrls.asset(project, asset[1], asset[2])}")`, cssValue(image.size) ?? "cover",
    cssValue(image.repeat) ?? "no-repeat", cssValue(image.position) ?? "center"]);
  if (!layers.length) return [];
  return [...decl("--pattern", cssValue(pattern.color)), `background-image: ${layers.map((layer) => layer[0]).join(", ")};`,
    `background-size: ${layers.map((layer) => layer[1]).join(", ")};`, `background-repeat: ${layers.map((layer) => layer[2]).join(", ")};`,
    `background-position: ${layers.map((layer) => layer[3]).join(", ")};`, ...decl("background-attachment", cssValue(image.attachment))];
}

/** Celý CSS náhledu Vzhledu pro `PreviewStyle`. */
export function appearanceCss(appearance: Appearance, project: string): string {
  const { text, colors, headings, lists, layout } = appearance;
  const heading = cssValue(text.heading.font);
  const out = [
    ...rule("", [...decl("background-color", cssValue(appearance.background.color)), ...decl("color", cssValue(colors.text)),
      ...decl("font-family", cssValue(text.body.font)), ...decl("font-size", length(text.body.size)), ...background(appearance, project)]),
    ...LEVELS.flatMap((level) => rule(" " + level, [...decl("font-family", heading), ...decl("font-size", length(headings[level].size)),
      ...decl("font-weight", cssValue(headings[level].weight)), ...decl("line-height", cssValue(cssLineHeight(headings[level].lineHeight ?? undefined))),
      ...decl("letter-spacing", length(headings[level].letterSpacing))])),
    ...rule(" .subheading", [...decl("font-family", cssValue(text.subheading.font)), ...decl("font-size", length(text.subheading.size))]),
    ...rule(" a", decl("color", cssValue(colors.link))),
    ...rule(" a:hover", decl("color", cssValue(colors.linkHover))),
    ...rule(" :focus-visible", colors.focus ? [`outline: 2px solid ${cssValue(colors.focus)};`, "outline-offset: 2px;"] : []),
    ...rule(" .ds-inverse", decl("color", cssValue(colors.textInverse))),
    ...rule(" ul", decl("list-style-type", cssValue(lists.marker))),
    ...rule(" ul, .ds-web ol", decl("padding-inline-start", length(lists.indent))),
    ...rule(" li::marker", decl("color", cssValue(lists.color))),
    ...rule(" .ds-container", [...decl("max-width", length(layout.contentSize)), ...decl("padding-inline", length(layout.gutter))]),
    ...rule(" .ds-container--wide", decl("max-width", length(layout.wideSize))),
  ];
  return out.join("\n");
}
