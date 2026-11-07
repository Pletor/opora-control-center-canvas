/**
 * Barva větve Linie (docs/navrhy/2026-11-06-linie-barvy-a-zamereni.md §1): pevné barvy main, develop, items, fix a
 * experiment; každý kořen feat má vlastní odstín z hashe jména a jeho děti ho dědí, s hloubkou bledší a světlejší.
 * Sdílí ji editor (řádky boardu) i Git graf (lanes). Čistá funkce bez Reactu.
 */
export type ColorRow = { branch?: string; name?: string; type?: string; role?: string; parent: string };

export const FIXED_COLOR: Record<string, string> = {
  main: "#4ade80", develop: "#60a5fa", items: "#c084fc", fix: "#f87171", hotfix: "#f87171", experiment: "#a39cc4",
};

// Řádek boardu bez větve (plánovaný) se pozná podle jména, lane Git grafu má jméno místo větve.
const keyOf = (row: ColorRow) => row.branch || row.name || "";
const fixedOf = (branch: string, row?: ColorRow) =>
  FIXED_COLOR[branch] ?? FIXED_COLOR[branch.split("/")[0]] ?? FIXED_COLOR[row?.type ?? row?.role ?? ""];

/** Stabilní řetězcový hash → odstín 0–359; stejné jméno dá při každém načtení stejnou barvu. */
export function hueOf(text: string): number {
  let hash = 0;
  for (const char of text) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return hash % 360;
}

export function branchColor(branch: string, rows: ColorRow[]): string {
  const byKey = new Map(rows.map((row) => [keyOf(row), row]));
  const fixed = fixedOf(branch, byKey.get(branch));
  if (fixed) return fixed;
  // Kořen = nejvyšší předek, který není pevný; neznámý rodič se bere jako develop (větev je sama kořenem).
  let root = branch, level = 0;
  for (let up = byKey.get(branch)?.parent; up && level < 20; up = byKey.get(up)?.parent) {
    const parent = byKey.get(up);
    if (!parent || fixedOf(up, parent)) break;
    root = up;
    level += 1;
  }
  // OP-123CD1.1: sytost a světlost podle prototypu Linie v3 (rebrand §10.1), dítě nese odstín kořene, jen světlejší.
  return `hsl(${hueOf(root)} ${Math.max(45, 75 - 9 * level)}% ${Math.min(80, 56 + 8 * level)}%)`;
}
