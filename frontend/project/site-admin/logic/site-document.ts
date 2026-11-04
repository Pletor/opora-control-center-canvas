// Dokument Správy webu projektu, jak ho vrací `GET /api/site-admin?project=` (kontrakt
// `docs/navrhy/2026-11-04-sprava-webu-design-system.md` §2, backend `backend/project/site_admin/`).
// Gramatika tokenů je formát Design System: hodnota barvy nebo stínu je řetězec (= první téma) nebo mapa
// `{téma: hodnota}`, alias je `{jiny-token}`. Server dokument normalizuje; frontend ho jen upravuje a posílá zpět.

export type Theme = { id: string; name: string };
export type ThemedValue = string | Record<string, string>;
export type Token = { name: string; value: ThemedValue; usage?: string };
export type TokenFamily = { note?: string; tokens: Token[] };
export type ColorFamily = { themes: Theme[]; tokens: Token[] };
export type FontFile = { family: string; file: string; weight: string | number; style: string };
export type TypeStyle = {
  name: string; fontSize: string; lineHeight?: string | number; fontWeight?: string | number;
  letterSpacing?: string; fontStyle?: string; family?: string; sample?: string; usage?: string;
};
export type TypeGroup = { name: string; family?: string; note?: string; styles: TypeStyle[] };
export type TypeFamily = { fonts: FontFile[]; families: Record<string, string>; groups: TypeGroup[] };
export type DesignTokens = {
  color: ColorFamily; type: TypeFamily;
  spacing?: TokenFamily; radius?: TokenFamily; shadow?: TokenFamily;
  [custom: string]: TokenFamily | ColorFamily | TypeFamily | undefined;
};
/** Komponenta systému: `preview` je HTML fragment pro sandbox iframe, `Button` skládá server z Tlačítek webu. */
export type DesignComponent = { name: string; group?: string; summary?: string; readme: string; preview: string; height: number };
/** Nahraný soubor skupiny assetů (`blob` = `assets/<skupina>/<soubor>`, záznam vrací `POST /assets`). */
export type AssetFile = { name: string; blob: string; size: number; type: string };
export type AssetGroup = { name: string; readme: string; files: AssetFile[] };
export type Design = {
  readme: string; sections: { slug: string; title: string; markdown: string }[]; tokens: DesignTokens;
  components: DesignComponent[]; assetGroups: AssetGroup[]; cover: unknown;
};
export type SiteDocument = {
  v: number; title: string; revision: number; lastChange: { by?: string; at?: string; note?: string } | null;
  settings: Record<string, unknown>; design: Design;
};

/** Rodiny s řádkem „jméno, hodnota, usage“ a vizuální ukázkou (spacing, radius, shadow). */
export type ScaleKind = "spacing" | "radius" | "shadow";

/** Hodnota tokenu v daném tématu: řetězec platí pro všechna témata, chybějící téma dědí z prvního. */
export function themedValue(value: ThemedValue, theme: string, first: string): string {
  if (typeof value === "string") return value;
  return value[theme] ?? value[first] ?? "";
}

/** Hodnota tokenu po změně jednoho tématu. Prázdná hodnota v jiném než prvním tématu znamená „dědí“;
 *  zbude-li jen první téma, mapa se složí zpět na řetězec. */
export function withThemeValue(value: ThemedValue, theme: string, next: string, themes: readonly Theme[]): ThemedValue {
  const first = themes[0]?.id ?? theme;
  const map: Record<string, string> = typeof value === "string" ? { [first]: value } : { ...value };
  if (next.trim() || theme === first) map[theme] = next.trim(); else delete map[theme];
  const keys = Object.keys(map).filter((id) => themes.some((item) => item.id === id));
  return keys.length === 1 && keys[0] === first ? map[first] : Object.fromEntries(keys.map((id) => [id, map[id]]));
}

/** Kolik čeho systém má: souhrn pro Overview a kartu na stránce projektu. */
export function designSummary(design: Design) {
  const tokens = design.tokens;
  const styles = tokens.type.groups.reduce((sum, group) => sum + group.styles.length, 0);
  return {
    themes: tokens.color.themes.length, colors: tokens.color.tokens.length, styles, fonts: tokens.type.fonts.length,
    families: Object.keys(tokens.type.families).length,
    spacing: tokens.spacing?.tokens.length ?? 0, radius: tokens.radius?.tokens.length ?? 0, shadow: tokens.shadow?.tokens.length ?? 0,
    components: design.components.length, assets: design.assetGroups.reduce((sum, group) => sum + group.files.length, 0),
  };
}
