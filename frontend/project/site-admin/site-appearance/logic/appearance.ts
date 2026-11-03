// Vzhled webu `settings.appearance` (kontrakt Správy webu §0 bod 3, backend `backend/project/site_admin/appearance.py`).
// Vzhled nemá vlastní data: server ho při čtení spočítá z tokenů a při uložení zapíše jen pole, která se liší od
// uložených tokenů; chybějící pole nemění, `null` token smaže. Frontend proto drží celý pohled a mění jen listy.

export type Leaf = string | number | null;
export type Level = "h1" | "h2" | "h3" | "h4" | "h5" | "h6";
export const LEVELS: Level[] = ["h1", "h2", "h3", "h4", "h5", "h6"];
type Heading = { size: Leaf; weight: Leaf; lineHeight: Leaf; letterSpacing: Leaf };

export type Appearance = {
  background: {
    color: Leaf;
    image: { asset: Leaf; size: Leaf; position: Leaf; repeat: Leaf; attachment: Leaf };
    pattern: { preset: Leaf; color: Leaf; scale: Leaf };
    overlay: { color: Leaf; opacity: Leaf };
  };
  text: { heading: { font: Leaf }; subheading: { font: Leaf; size: Leaf }; body: { font: Leaf; size: Leaf } };
  colors: { text: Leaf; textInverse: Leaf; link: Leaf; linkHover: Leaf; focus: Leaf };
  headings: Record<Level, Heading>;
  lists: { marker: Leaf; color: Leaf; indent: Leaf };
  layout: { contentSize: Leaf; wideSize: Leaf; gutter: Leaf };
};

const heading = (): Heading => ({ size: null, weight: null, lineHeight: null, letterSpacing: null });
export const EMPTY_APPEARANCE: Appearance = {
  background: {
    color: null, image: { asset: null, size: null, position: null, repeat: null, attachment: null },
    pattern: { preset: null, color: null, scale: null }, overlay: { color: null, opacity: null },
  },
  text: { heading: { font: null }, subheading: { font: null, size: null }, body: { font: null, size: null } },
  colors: { text: null, textInverse: null, link: null, linkHover: null, focus: null },
  headings: { h1: heading(), h2: heading(), h3: heading(), h4: heading(), h5: heading(), h6: heading() },
  lists: { marker: null, color: null, indent: null },
  layout: { contentSize: null, wideSize: null, gutter: null },
};

type Tree = { [key: string]: Tree | Leaf };
const isTree = (value: unknown): value is Tree => !!value && typeof value === "object" && !Array.isArray(value);

function merge(base: Tree, raw: unknown): Tree {
  const given = isTree(raw) ? raw : {};
  return Object.fromEntries(Object.entries(base).map(([key, value]) => {
    const next = given[key];
    if (isTree(value)) return [key, merge(value, next)];
    return [key, typeof next === "string" || typeof next === "number" ? next : null];
  }));
}

/** Vzhled ze settings dokumentu; chybějící list je `null` (tvar je vždy celý, i u starého dokumentu). */
export function readAppearance(settings: Record<string, unknown>): Appearance {
  return merge(EMPTY_APPEARANCE as unknown as Tree, settings.appearance) as unknown as Appearance;
}

/** Hodnota listu podle cesty `background.pattern.scale`. */
export function field(appearance: Appearance, path: string): Leaf {
  let node: Tree | Leaf = appearance as unknown as Tree;
  for (const part of path.split(".")) node = isTree(node) ? node[part] ?? null : null;
  return isTree(node) ? null : node;
}

/** Vzhled po změně jednoho listu. Prázdný text = `null` (server token smaže); čísla zůstanou čísly. */
export function withField(appearance: Appearance, path: string, value: Leaf): Appearance {
  const leaf = typeof value === "string" && !value.trim() ? null : typeof value === "string" ? value.trim() : value;
  const set = (node: Tree, parts: string[]): Tree => {
    const [head, ...rest] = parts;
    return { ...node, [head]: rest.length ? set(isTree(node[head]) ? node[head] as Tree : {}, rest) : leaf };
  };
  return set(appearance as unknown as Tree, path.split(".")) as unknown as Appearance;
}

/** Číslo z pole (měřítko vzorku, krytí překryvu); prázdné nebo nečíselné = `null`. */
export function numberLeaf(text: string): number | null {
  const value = Number(text.replace(",", "."));
  return text.trim() && Number.isFinite(value) ? value : null;
}

/** Soubory assetů projektu, které můžou být obrázkem pozadí (`assets/<skupina>/<soubor>`). */
export function imageAssets(groups: { name: string; files: unknown[] }[]): string[] {
  return groups.flatMap((group) => group.files.flatMap((file) => {
    const item = file as { blob?: string; type?: string };
    return item.blob && (!item.type || item.type.startsWith("image/")) ? [item.blob] : [];
  }));
}
