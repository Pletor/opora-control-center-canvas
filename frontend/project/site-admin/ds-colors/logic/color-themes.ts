// Témata barev: přidat, přejmenovat, posunout, odebrat (nejvýš 8, `id` podle gramatiky formátu). První téma je
// výchozí (`:root`) a zdroj dědění: přesun nebo odebrání prvního tématu dědění přepíše tak, aby žádná barva
// nezměnila hodnotu. Stíny s hodnotou per téma srovná server (neznámé téma zahodí s poznámkou).
import type { ColorFamily, Theme } from "@/project/site-admin/logic/site-document";

export const MAX_THEMES = 8;

/** `id` z názvu: malá písmena bez diakritiky, mezery na pomlčky; obsazené dostane číslo. */
export function themeId(name: string, themes: readonly Theme[]): string {
  const base = name.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9_.-]+/g, "-").replace(/^[^a-z0-9]+|-+$/g, "").slice(0, 60) || "theme";
  const taken = themes.map((theme) => theme.id);
  if (!taken.includes(base)) return base;
  for (let index = 2; ; index++) if (!taken.includes(`${base}-${index}`)) return `${base}-${index}`;
}

export function addTheme(family: ColorFamily, name: string): ColorFamily {
  if (family.themes.length >= MAX_THEMES || !name.trim()) return family;
  return { ...family, themes: [...family.themes, { id: themeId(name, family.themes), name: name.trim() }] };
}

export function renameTheme(family: ColorFamily, id: string, name: string): ColorFamily {
  return { ...family, themes: family.themes.map((theme) => theme.id === id ? { ...theme, name } : theme) };
}

/** Posun tématu o `step` (−1 nahoru, +1 dolů). Změní-li se první téma, mapa hodnot se doplní o všechna témata,
 *  která dosud dědila, aby žádná barva nezměnila hodnotu. */
export function moveTheme(family: ColorFamily, id: string, step: number): ColorFamily {
  const from = family.themes.findIndex((theme) => theme.id === id), to = from + step;
  if (from < 0 || to < 0 || to >= family.themes.length) return family;
  const themes = [...family.themes];
  [themes[from], themes[to]] = [themes[to], themes[from]];
  const before = family.themes[0].id, after = themes[0].id;
  if (before === after) return { ...family, themes };
  const tokens = family.tokens.map((token) => {
    if (typeof token.value === "string") return token;
    const value = { ...token.value };
    for (const theme of themes) value[theme.id] ??= value[before];
    return { ...token, value };
  });
  return { themes, tokens };
}

/** Odebere téma i jeho hodnoty; poslední téma zůstává. */
export function removeTheme(family: ColorFamily, id: string): ColorFamily {
  if (family.themes.length <= 1) return family;
  const themes = family.themes.filter((theme) => theme.id !== id);
  const tokens = family.tokens.map((token) => {
    if (typeof token.value === "string") return token;
    const value = { ...token.value };
    if (id === family.themes[0].id) value[themes[0].id] ??= value[id];
    delete value[id];
    const keys = Object.keys(value);
    return { ...token, value: keys.length === 1 && keys[0] === themes[0].id ? value[keys[0]] : value };
  });
  return { themes, tokens };
}
