# Vzhled webu

Část „Vzhled webu“ Správy webu (kontrakt `docs/navrhy/2026-11-04-sprava-webu-design-system.md` §0 bod 3, §2) nad `settings.appearance`. Vzhled je jen pohled na tokeny: server ho počítá z `design.tokens` a při uložení zapíše jen změněná pole (`backend/project/site_admin/appearance.py`, tabulka polí v jeho README). Prázdné pole pošle `null`, server token smaže.

- `components/AppearanceSection.tsx` (rodič dílku): skládá editory a náhled, celý nový Vzhled hlásí `onChange` nahoru; ukládá `SiteAdmin`.
- `components/BackgroundEditor.tsx`: barva, obrázek z Assets (velikost, poloha, opakování, scroll/fixed), vzorek (tečky, mřížka, linky, šikmé, barva, měřítko), překryv a krytí.
- `components/TextEditor.tsx`: písmo nadpisů, podnadpisů a textů (stack, nabídka rodin z Typography), velikosti, barvy textu, inverzního textu, odkazů, odkazu po najetí a focusu.
- `components/HeadingsEditor.tsx`: H1–H6 (velikost, váha, řádkování, prostrkání) a odrážky (styl, barva, odsazení).
- `components/AppearancePreview.tsx`: ukázková stránka v `TokensScope` s třídou `.ds-web`.
- `logic/appearance.ts` (+ test): tvar, čtení s doplněním `null`, změna listu podle cesty, čísla, obrázkové assety.
- `logic/appearance-css.ts` (+ test): CSS náhledu z rozepsaného Vzhledu (stejná pravidla jako `@layer base` serveru), takže neuložená změna je vidět hned.
