/**
 * Strom větví Linie (docs/navrhy/2026-11-06-linie-strom-vetvi.md): zrcadlo `tree.py`. Rodič se čte ze jména:
 * feat/a-b-c → nejdelší existující prefix na hranici `-`, jinak develop; items/* → develop; develop → main.
 * `null` = jméno rodiče neurčuje (main, fix/*, experiment/*), rozhoduje práce.
 */
export function parentOf(branch: string, heads: string[]): string | null {
  const name = branch.trim();
  if (name === "develop") return "main";
  if (name.startsWith("items/")) return "develop";
  if (name.startsWith("hotfix/")) return "main";
  if (!name.startsWith("feat/")) return null;
  for (let cut = name.lastIndexOf("-"); cut > "feat/".length; cut = name.lastIndexOf("-", cut - 1)) {
    const prefix = name.slice(0, cut);
    if (heads.includes(prefix)) return prefix;
  }
  return "develop";
}

/** Počet předků po řetězu rodičů (main 0, develop 1); neodvozená větev je 0. */
export function depthOf(branch: string, heads: string[]): number {
  let depth = 0;
  for (let at = parentOf(branch, heads); at !== null && depth < 20; at = parentOf(at, heads)) depth += 1;
  return depth;
}
