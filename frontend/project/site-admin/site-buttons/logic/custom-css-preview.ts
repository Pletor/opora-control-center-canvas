// Náhled neuloženého vlastního CSS tlačítka. Pravdu má server (`custom_css.py`, tinycss2, 422 s řádkem při Uložit);
// tady jde jen o to, aby animace a pseudo-elementy byly vidět hned při psaní, a přitom nic nevyteklo do OPORY.
// Proto stejný přepis jako na serveru: `:scope` = tlačítko, jiný selektor je jeho potomek, `@keyframes x` →
// `ds-btn-<varianta>-x`, url jen `assets/…`. Co by pravidlo mohlo opustit (neuzavřená závorka, `<`, `\`, zakázané
// at-rules a selektory), náhled odmítne s řádkem a CSS do stránky nepustí.
import { assetUrls, splitSelectors } from "@/project/site-admin/ds-preview/logic/components-scope";

export type PreviewProblem = { line: number; reason: string };
type Block = { prelude: string; inner: string; line: number; innerLine: number };

const lineAt = (text: string, index: number) => text.slice(0, index).split("\n").length;
const FORBIDDEN_SELECTOR = /(?:^|[\s>+~(,])(?:html|body)(?![\w-])|:root|:host|\*/i;

class Problem extends Error { constructor(readonly line: number, reason: string) { super(reason); } }

/** Pravidla nejvyšší úrovně textu: předpona a obsah mezi párovými závorkami. */
function blocks(text: string, base: number): Block[] {
  const out: Block[] = [];
  let depth = 0, quote = "", start = 0, open = 0;
  for (let index = 0; index < text.length; index++) {
    const char = text[index];
    if (quote) { if (char === quote) quote = ""; continue; }
    if (char === '"' || char === "'") quote = char;
    else if (char === "{") { if (depth++ === 0) open = index; }
    else if (char === "}") {
      if (--depth < 0) throw new Problem(base + lineAt(text, index) - 1, "Přebývá zavírací závorka }.");
      if (depth === 0) {
        const raw = text.slice(start, open);
        const lead = raw.length - raw.trimStart().length;
        out.push({ prelude: raw.trim(), inner: text.slice(open + 1, index), line: base + lineAt(text, start + lead) - 1, innerLine: base + lineAt(text, open + 1) - 1 });
        start = index + 1;
      }
    }
  }
  if (depth > 0) throw new Problem(base + lineAt(text, open) - 1, "Chybí zavírací závorka }.");
  if (text.slice(start).trim()) throw new Problem(base + lineAt(text, start) - 1, "Deklarace mimo pravidlo; napiš ji do :scope { … }.");
  return out;
}

function rules(text: string, base: number, root: string, prefix: string, names: Set<string>, depth: number): string[] {
  const out: string[] = [];
  for (const node of blocks(text, base)) {
    const keyword = node.prelude.match(/^@([a-z-]+)/i)?.[1].toLowerCase();
    if (keyword === "keyframes") {
      out.push(`@keyframes ${prefix}-${node.prelude.split(/\s+/)[1]} {${node.inner}}`);
    } else if (keyword === "media" || keyword === "supports" || keyword === "container") {
      if (depth >= 3) throw new Problem(node.line, "Vnoření nejvýš 3 úrovně.");
      out.push(`${node.prelude} {`, ...rules(node.inner, node.innerLine, root, prefix, names, depth + 1), "}");
    } else if (keyword) {
      throw new Problem(node.line, `@${keyword} není povolené (jen @keyframes, @media, @supports, @container).`);
    } else {
      if (node.inner.includes("{")) throw new Problem(node.innerLine, "Vnořená pravidla nejsou povolená, napiš je jako samostatný selektor.");
      const selectors = splitSelectors(node.prelude);
      const bad = selectors.find((selector) => FORBIDDEN_SELECTOR.test(selector));
      if (!selectors.length) throw new Problem(node.line, "Prázdný selektor.");
      if (bad) throw new Problem(node.line, `Selektor ${bad} míří mimo tlačítko (html, body, :root, :host, * nejsou povolené).`);
      const body = node.inner.replace(/(animation(?:-name)?\s*:)([^;]*)/gi, (_all, property: string, value: string) =>
        property + value.replace(/[A-Za-z_-][\w-]*/g, (word) => names.has(word) ? `${prefix}-${word}` : word));
      out.push(`${selectors.map((selector) => selector.includes(":scope") ? selector.replaceAll(":scope", root) : `${root} ${selector}`).join(", ")} {${body}}`);
    }
  }
  return out;
}

/** Vlastní CSS varianty → CSS pod `.ds-web .ds-btn--<varianta>`, nebo problém s řádkem. */
export function customCssPreview(slug: string, text: string, project: string): { css: string } | { problem: PreviewProblem } {
  const clean = text.replace(/\/\*[\s\S]*?\*\//g, (comment) => comment.replace(/[^\n]/g, " "));
  const bad = clean.split("\n").findIndex((row) => /[<\\]|@import|expression\s*\(|javascript:/i.test(row) || /url\(\s*(?!["']?assets\/)/i.test(row));
  if (bad >= 0) return { problem: { line: bad + 1, reason: "Tohle náhled ani server nepustí (<, \\, @import, expression, javascript: nebo url mimo assets/)." } };
  const names = new Set([...clean.matchAll(/@keyframes\s+([A-Za-z_-][\w-]*)/gi)].map((match) => match[1]));
  try {
    return { css: assetUrls(rules(clean, 1, `.ds-web .ds-btn--${slug}`, `ds-btn-${slug}`, names, 1).join("\n"), project) };
  } catch (failure) {
    if (failure instanceof Problem) return { problem: { line: failure.line, reason: failure.message } };
    throw failure;
  }
}

/** „Omezit pohyb“: stejné vypnutí animací a přechodů, jaké server přidává pro `prefers-reduced-motion: reduce`,
 *  jednou pro skutečné nastavení systému a jednou pro přepínač náhledu (`.ds-web--still`). */
const still = (root: string) => ["", "::before", "::after", " *", " *::before", " *::after"].map((part) => `${root} .ds-btn${part}`).join(", ")
  + " { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; }";
export const REDUCED_MOTION_CSS = `${still(".ds-web.ds-web--still")}
@media (prefers-reduced-motion: reduce) { ${still(".ds-web")} }`;
