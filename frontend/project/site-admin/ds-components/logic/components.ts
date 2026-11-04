// Komponenty design systému (`design.components`, backend `design_system._components`): seznam po skupinách,
// kontrola jména a náhledu stejná jako na serveru a dokument náhledu pro iframe `sandbox=""`. Náhled je HTML
// fragment webu projektu, proto dostane vlastní dokument s `tokens.css` a `components.css` uložené revize, téma
// atributem `data-theme` na `<html>` a CSP, která pustí jen styly a obrázky a fonty z OPORY. Skripty sandbox nespustí.
import type { DesignComponent } from "@/project/site-admin/logic/site-document";
import { siteAdminUrls } from "@/project/site-admin/logic/site-admin-api";
import { assetUrls } from "@/project/site-admin/ds-preview/logic/components-scope";
import { TOKEN_NAME, freeName } from "@/project/site-admin/logic/token-names";

/** Komponentu `Button` skládá server z Tlačítek webu, na stránce se jen ukazuje. */
export const GENERATED = "Button";
export const OTHER_GROUP = "Ostatní";
// Stejný filtr jako `UNSAFE_MARKUP` v `backend/project/site_admin/design_system.py` (a SVG assetu).
const UNSAFE = /<script|<foreignobject|[\s/"']on[a-z]+\s*=|javascript:|&#|<iframe|<embed|<object/i;
const MIN_HEIGHT = 40, MAX_HEIGHT = 4000;

export const isGenerated = (component: DesignComponent) => component.name === GENERATED;

/** Skupiny v pořadí prvního výskytu; komponenta bez skupiny jde do „Ostatní“ na konec. */
export function groupComponents(list: readonly DesignComponent[]): { group: string; items: DesignComponent[] }[] {
  const groups = new Map<string, DesignComponent[]>();
  for (const component of list) {
    const group = component.group?.trim() || OTHER_GROUP;
    groups.set(group, [...(groups.get(group) ?? []), component]);
  }
  return [...groups].map(([group, items]) => ({ group, items }))
    .sort((a, b) => Number(a.group === OTHER_GROUP) - Number(b.group === OTHER_GROUP));
}

/** Proč jméno neprojde, nebo `""`; `own` je současné jméno (smí zůstat). */
export function componentNameProblem(name: string, taken: readonly string[], own = ""): string {
  if (!TOKEN_NAME.test(name)) return "Jméno: písmena, číslice, _ . -, nejvýš 64 znaků.";
  if (name === GENERATED && own !== GENERATED) return "Button skládá server z Tlačítek webu.";
  if (name !== own && taken.includes(name)) return `Komponenta ${name} už v systému je.`;
  return "";
}

/** Proč server náhled odmítne, nebo `""`. */
export const previewProblem = (html: string) =>
  UNSAFE.test(html) ? "Náhled bez skriptů, obsluh událostí (on…=), javascript:, &# a vnořeného obsahu (iframe, embed, object)." : "";

/** Výška náhledu v mezích serveru (40–4000 px); nečíslo je 120. */
export function clampHeight(value: number): number {
  return Number.isFinite(value) ? Math.min(MAX_HEIGHT, Math.max(MIN_HEIGHT, Math.round(value))) : 120;
}

export function newComponent(taken: readonly string[]): DesignComponent {
  const name = freeName("Component", [...taken, GENERATED]);
  return { name, group: "", readme: `# ${name}\n\nK čemu je a kdy ji použít.\n\n## Kdy ne\n\n`, preview: '<div class="body" style="padding: 16px">Ukázka</div>', height: 120 };
}

const attribute = (value: string) => value.replace(/[&"<>]/g, (char) => `&#${char.charCodeAt(0)};`);
const closeStyle = (css: string) => css.replace(/<\/style/gi, "<\\/style");
const FONT_URL = /url\("fonts\/([^"]+)"\)/g;
const ASSET_ATTRIBUTE = /\b(src|href)=(["'])assets\/([^"'/]+)\/([^"']+)\2/g;

/** Celý dokument pro `srcdoc`: CSP, `tokens.css` s fonty z API, `components.css` s assety z API a náhled. */
export function previewDocument({ html, tokensCss, componentsCss, theme, project, origin }: {
  html: string; tokensCss: string; componentsCss: string; theme: string; project: string; origin: string;
}): string {
  const csp = `default-src 'none'; style-src 'unsafe-inline'; img-src ${origin} data:; font-src ${origin}; media-src ${origin}`;
  const tokens = tokensCss.replace(FONT_URL, (_all, name: string) => `url("${origin}${siteAdminUrls.font(project, name)}")`);
  const components = assetUrls(componentsCss, project).replace(/url\("\/api\//g, `url("${origin}/api/`);
  const body = html.replace(ASSET_ATTRIBUTE, (_all, name: string, quote: string, group: string, file: string) =>
    `${name}=${quote}${origin}${siteAdminUrls.asset(project, group, file)}${quote}`);
  return `<!doctype html><html data-theme="${attribute(theme)}"><head><meta charset="utf-8">`
    + `<meta http-equiv="Content-Security-Policy" content="${attribute(csp)}">`
    + `<style>html,body{margin:0}</style><style>${closeStyle(tokens)}</style><style>${closeStyle(components)}</style>`
    + `</head><body>${body}</body></html>`;
}
