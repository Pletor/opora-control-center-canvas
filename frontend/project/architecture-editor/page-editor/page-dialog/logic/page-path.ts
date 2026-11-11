// Adresa nové stránky předvyplněná z názvu: malá písmena bez diakritiky, mezery a znaky na pomlčky,
// podstránka pod cestou rodiče („Členská sekce“ pod /kurz → /kurz/clenska-sekce). Bez Reactu, test vedle.
export function pathFromName(name: string, parentPath = ""): string {
  const slug = name.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  const base = parentPath.replace(/\/+$/, "");
  return slug ? `${base}/${slug}` : base || "/";
}
