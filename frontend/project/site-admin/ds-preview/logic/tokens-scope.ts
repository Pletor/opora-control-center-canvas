// Vygenerovaný `tokens.css` projektu (server, `backend/project/site_admin/compile.py`) uvnitř náhledu v OPOŘE.
// Soubor je psaný pro web projektu: `:root`, `[data-theme="…"]` a třídy stylů (`.body`) by v aplikaci přebily
// její vlastní tokeny (`--ink`, `--surface`) i třídy. Proto se každý selektor uzavře do `.ds-scope`, téma se přepíná
// atributem `data-theme` na náhledu a cesta k fontům `fonts/<soubor>` míří na `GET /api/site-admin/fonts/<soubor>`.
import { siteAdminUrls } from "@/project/site-admin/logic/site-admin-api";

export const SCOPE = "ds-scope";

function scopeSelector(selector: string): string {
  return selector.split(",").map((part) => {
    const one = part.trim();
    if (one === ":root") return "." + SCOPE;
    if (one.startsWith("[data-theme")) return "." + SCOPE + one;
    return "." + SCOPE + " " + one;
  }).join(", ");
}

/** `tokens.css` uzavřený do `.ds-scope` a s fonty z API projektu. Rozvržení je pevné (jeden selektor na řádek
 *  s `{` na konci, `@font-face` bez selektoru), takže stačí přepis po řádcích. */
export function scopeTokensCss(css: string, project: string): string {
  return css.split("\n").map((line) => {
    const font = line.match(/^(\s*src: url\(")fonts\/([^"]+)("\).*)$/);
    if (font) return font[1] + siteAdminUrls.font(project, font[2]) + font[3];
    const block = line.match(/^([^\s@/][^{]*)\{$/);
    return block ? scopeSelector(block[1]) + " {" : line;
  }).join("\n");
}

/** CSS délka z hodnoty tokenu: číslo = px (jako v serveru), jinak beze změny. */
export function cssLength(value: string | number | undefined): string | undefined {
  if (value === undefined || value === "") return undefined;
  const text = String(value).trim();
  return /^-?\d+(\.\d+)?$/.test(text) && Number(text) !== 0 ? text + "px" : text;
}

/** Řádkování: bezrozměrné číslo pod 10 zůstane násobkem, jinak délka. */
export function cssLineHeight(value: string | number | undefined): string | undefined {
  if (value === undefined || value === "") return undefined;
  const text = String(value).trim();
  return /^\d+(\.\d+)?$/.test(text) && Number(text) < 10 ? text : cssLength(text);
}
