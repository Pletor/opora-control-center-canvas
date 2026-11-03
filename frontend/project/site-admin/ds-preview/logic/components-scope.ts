// Vygenerovaný `components.css` projektu (server, `backend/project/site_admin/compile.py`) uvnitř náhledu v OPOŘE.
// Soubor stylizuje web projektu (`body`, `h1`, `a`, `.ds-btn`), takže by v aplikaci přepsal její vlastní prvky.
// Proto každý selektor dostane kořen `.ds-web` (náhled webu, nese i `.ds-scope` s tokeny): `body` je kořen sám,
// ostatní jsou jeho potomci. Vrstvy `@layer` se rozbalí, protože styl ve vrstvě vždy prohraje s nevrstveným stylem
// aplikace (reset tlačítek a odkazů by přebil tlačítka webu); pořadí base → components → custom zůstane pořadím
// v souboru. Obrázky `url("assets/…")` míří na API projektu, jinak by se relativní cesta ztratila.
import { siteAdminUrls } from "@/project/site-admin/logic/site-admin-api";

export const WEB = "ds-web";
const ROOT = "." + WEB;

/** Seznam selektorů podle čárek nejvyšší úrovně; čárky v `:not(a, b)` nebo `[x="a,b"]` zůstanou. */
export function splitSelectors(text: string): string[] {
  const parts: string[] = [];
  let depth = 0, quote = "", start = 0;
  for (let index = 0; index < text.length; index++) {
    const char = text[index];
    if (quote) { if (char === quote) quote = ""; continue; }
    if (char === '"' || char === "'") quote = char;
    else if (char === "(" || char === "[") depth++;
    else if (char === ")" || char === "]") depth--;
    else if (char === "," && depth === 0) { parts.push(text.slice(start, index)); start = index + 1; }
  }
  parts.push(text.slice(start));
  return parts.map((part) => part.trim()).filter(Boolean);
}

/** Selektor webu → selektor náhledu: `body` a `:root` jsou kořen `.ds-web`, ostatní jeho potomci. */
export function scopeWebSelector(selector: string, root = ROOT): string {
  return splitSelectors(selector).map((one) => {
    if (one === "body" || one === ":root" || one === "html") return root;
    if (/^body[:.[]/.test(one)) return root + one.slice(4);
    return root + " " + one;
  }).join(", ");
}

const ASSET_URL = /url\(\s*["']?assets\/([^"'/)]+)\/([^"')]+?)["']?\s*\)/g;

/** `url("assets/<skupina>/<soubor>")` → adresa assetu v API projektu. */
export function assetUrls(css: string, project: string): string {
  return css.replace(ASSET_URL, (_all, group: string, name: string) => `url("${siteAdminUrls.asset(project, group, name)}")`);
}

/** `components.css` uzavřený do `.ds-web`. Rozvržení je pevné (selektor na řádku s `{` na konci, vrstva na sloupci 0),
 *  takže stačí přepis po řádcích; kroky `@keyframes` (`from`, `50%`) se nepřepisují. */
export function scopeComponentsCss(css: string, project: string): string {
  const out: string[] = [];
  let layer = false, frames = -1;
  for (const line of css.split("\n")) {
    if (/^@layer [^{]*;\s*$/.test(line)) continue;
    if (/^@layer [^{]*\{\s*$/.test(line)) { layer = true; continue; }
    if (layer && line === "}") { layer = false; continue; }
    const indent = line.length - line.trimStart().length;
    if (frames >= 0) {
      out.push(line);
      if (line.trim() === "}" && indent === frames) frames = -1;
      continue;
    }
    if (/^\s*@keyframes\s/.test(line)) { frames = indent; out.push(line); continue; }
    const block = line.match(/^(\s*)([^\s@}/][^{]*)\{\s*$/);
    out.push(assetUrls(block ? block[1] + scopeWebSelector(block[2].trim()) + " {" : line, project));
  }
  return out.join("\n");
}
