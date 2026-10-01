# Panely Editoru: Knihovna, Agenti a postupy, lišta módů

Kontrakt pro přestavbu levého a pravého panelu Editoru. Návrh (7 artboardů, schválen 2026-09-16) je v Claude Design:
https://claude.ai/design/p/12f7db47-989c-46c5-8498-aa12e01f8408?file=Panely+Editoru.dc.html

Mění se **forma**, ne informační architektura: názvy záložek, kategorií, sekcí a stavové klíče zůstávají. Kód provádí tento kontrakt, nemění ho.

## Proč

Panely jsou dnes malé (písmo 0.75rem, řádky 31 px), kategorie se liší jen textem, sbalená lišta neříká, co v ní je. Uživatel se v pracovním prostoru neorientuje.

## Společné míry (platí pro všechny tři dílky)

| Míra | Hodnota |
|---|---|
| Základní písmo panelu | 14px, řádkování 1.35 |
| Název položky | 14px, váha 600 |
| Popis, metadata | 13px, `--ink-muted`; značky (pill) 11px |
| Nadpis sekce | 11px, váha 700, verzálky, prostrkání 0.1em |
| Záložky | 12px, váha 700, verzálky, 0.08em, aktivní = `--accent` + spodní linka 2px |
| Hlavička panelu | 48px, název 15px/700 |
| Hledání | 36px, ikona ⌕, tichý počet nálezů vpravo |
| Řádek seznamu / kategorie | min. 40px; barevný proužek 3px na levé hraně (`border-left`) |
| Ikona kategorie | žeton 28px (rádius 8px), znak 15px, barva `--c`, podklad `color-mix(in srgb, var(--c) var(--cat-soft), transparent)` |
| Panel rozbalený / sbalený | 304px / 48px |
| Sbalená lišta | ikony 34px, aktivní = plný žeton v barvě kategorie + proužek 3px u hrany, hover = obrys 2px + tooltip (`title`) |
| Lišta módů | 64px, ikona 20px nad popiskem 10.5px, aktivní = podklad `--accent-soft`, text `--accent` |
| Rádius | 6px prvky, 10px dlaždice |
| Kontrast | text 4.5:1 (nikdy poloprůhledný text) |

Barvy kategorií jsou tokeny v `frontend/design-tokens/styles/theme-tokens.css` (`--cat-<id>`, `--cat-soft`), světlý i tmavý režim. Dílek je používá jen přes BEM variantu, která nastaví `--c`, např. `.library-navbar__category--backend { --c: var(--cat-backend); }`. Žádné nové barvy mimo tokeny.

### Ikony (lineární SVG sada `frontend/ui-kit/icon/`, jména z Lucide)

| Kategorie bloků (id → ikona) | Kategorie postupů (id → ikona) | Módy plátna (id → ikona) |
|---|---|---|
| fe-components component | workflows workflow | structure layout-grid |
| fe-logic function-square | pipelines link | text type |
| fe-css palette | rules scale | drawing pencil |
| backend server | hooks terminal | map map |
| database database | skills sparkles | agents bot |
| cache refresh-cw | agents users | Knihovna library |
| security shield | | |
| cloud cloud | | |
| tests check-circle | | |

Sekce zadání karty: Cíl a konec target, Harness cpu, Smyčka repeat, Předávky arrow-left-right, Pracovní prostor folder. Strom vrstev: sektor layout-grid, uzel component, oblast map, domeček home. Ovládání: panel-left-open/close, panel-right-open/close, chevron-left/right, search, grip-vertical. Ikona i barva se odvozují v `logic/` (čistá funkce s testem, vrací jméno ikony), komponenta jen mapuje na `<Icon>`.

## Dílek 1: lišta módů (`frontend/layout/mode-rail/`)

- Nová `logic/mode-rail.ts` + test: `modeIcon(id)` vrací jméno ikony z tabulky, neznámý id → `layout-grid`.
- `ModeRail.tsx`: každý mód = tlačítko s `<span class="mode-rail__glyph">` nad `<span class="mode-rail__label">`. Tlačítko Knihovna stejně, s rámečkem a stavem `--active`, když je panel otevřený.
- Styl zůstává v `layout/shell/styles/workspace-modes.css` (blok `.mode-rail`), 64px, BEM, příběhový komentář.

## Dílek 2: Knihovna (`frontend/layout/library-navbar/`)

- Stav dostane `expanded: boolean` (výchozí `true`). `open=false` = panel není vidět (jako dnes), `open=true, expanded=false` = lišta 48px. Akce `toggleExpanded`, `expandToCategory(state, category)` = expanded, tab obsah, mode bloky, kategorie otevřená. Parse tolerantní jako dnes. Testy vedle.
- Nový dílek `components/LibraryNavbarRail.tsx`: tlačítko rozbalit ⇥ nahoře, pod ním 9 ikon kategorií (`title` = název · počet). Klik hlásí `onExpandToCategory(id)`.
- `LibraryNavbar.tsx` vykreslí lištu, nebo rozbalený panel; hlavička dostane tlačítko sbalit ⇤.
- Kategorie (`LibraryCategories`): řádek 40px, ikona-žeton, název 600, počet tabulárně, šipka › / ‹ u otevřené; otevřená = podklad `color-mix(var(--c) 10%)`, název v `--c`.
- Dlaždice (`LibraryTiles`): ikona-žeton vlevo nahoře, název 600, popis 13px, značky dole („3 dílky“ v barvě kategorie, „5 pravidel“ neutrální), úchyt ⋮⋮ vpravo nahoře; proužek 3px v barvě kategorie.
- Strom (STRÁNKA): řádky 40px, odsazení 24px na úroveň, značka druhu jako žeton 24px, domeček ⌂ jako značka, skrytá karta ztlumená (opacity 0.55 na celém řádku, ne na textu zvlášť).
- Šířka 304px; `library-navbar.css` se přepíše podle měr výše. Nezasahovat do katalogu (`editor/component-library/`).

## Dílek 3: Agenti a postupy (`frontend/layout/agent-navbar/`)

- `--agent-navbar-w`: 304px rozbaleno, 48px sbaleno. `body` padding-right zůstává navázaný na token.
- Lišta (`AgentNavbarRail`): tlačítko ⇤ nahoře, ikony 34px v barvě kategorie, aktivní plný žeton + proužek u pravé hrany.
- Katalog: kategorie jako svislý seznam řádků 40px (ne wrap čipů), ikona-žeton, název, počet. Pod hledáním nadpis sekce „<Kategorie> · N“. Položky jako řádky: ikona-žeton 24px, název 600, popis 13px jednořádkový s výpustkou, značka „N kroků“, úchyt ⋮⋮; druh `info` (hook, skill) ztlumený a bez úchytu.
- Agenti (brief): hlavička název 15px + značky (druh v barvě kategorie fe-components, fáze v barvě agents, otevřeno neutrální); poznámka „Jen ke čtení“ v `--gold-soft`/`--gold`; každá z pěti sekcí jako rámeček s hlavičkou 38px (ikona-žeton, název 13.5px/600, meta vpravo) a tělem 13px. Pořadí sekcí beze změny. Dvě tlačítka dole, primární v `--accent`.
- Glyfy kategorií v `logic/agent-navbar.ts` se nahradí tabulkou výše; test upravit.

## Doladění po první implementaci (2026-09-16)

> Body 1, 2, 5 a 6 nahrazuje `docs/rozvrzeni-editoru.md` (2026-09-17): Knihovna i Agenti a postupy jsou zavěšené panely pod tlačítkem v liště nástrojů, ne sloupce v toku, nesbalují se na lištu 48 px a lišta módů je vodorovná řada záložek.

1. **Skladba prostoru.** Editor je jeden rám `editor-frame` se sloupci: lišta módů 64px · Knihovna (304px / 48px) · shell (plátno + inspektor) · Agenti a postupy (304px / 48px). Knihovna ani Agenti nejsou absolutní ani fixní; oba začínají pod horní lištou a nic nepřekrývají. Šířky sloupců drží tokeny `--library-navbar-w` a `--agent-navbar-w`, hodnoty přepíná modifikátor `--collapsed` na panelu.
2. **Jeden způsob schování.** Panel se sbalí na lištu 48px; nikdy nezmizí úplně. Stav Knihovny má jen `expanded` (`open` a `closePanel` se ruší, uložený `open` se při parse ignoruje). Tlačítko Knihovna na liště módů přepíná `expanded` a svítí, když je panel rozbalený. Křížek v hlavičce Knihovny se ruší, zůstává ⇤ sbalit.
3. **Zkratky.** Ctrl+Shift+. sbalí Agenty a postupy (dnes), Ctrl+Shift+, sbalí Knihovnu. Obě pravidla v `logic/` s testem, obě registruje `App`.
4. **Ikony.** Jedna lineární SVG sada v `frontend/ui-kit/icon/` (dílek `Icon`, `logic/icon-paths.ts` s cestami, `size` 16/20/24, `stroke: currentColor`, `stroke-width: 1.75`, `aria-hidden`). Sada Lucide (ISC), cesty vložené ručně jen pro použité ikony. Mapování id → ikona zůstává v `logic/` každého panelu (`modeIcon`, `categoryIcon` vrací jméno ikony). Unicode glyfy se ruší.
5. **Tooltip sbalené lišty.** Vlastní dílek `ui-kit/tooltip/` (název · počet), zobrazí se hned na hover/focus, umístěný vedle lišty, `role="tooltip"`; nativní `title` se ruší.
6. **Úzká okna.** Pod 1100px se oba panely automaticky sbalí (jen vzhled, uložený stav se nemění); pod 760px se lišta módů nepřeklápí do řádku, zůstává sloupec.

## Co se nemění

Stavové klíče localStorage, zkratka Ctrl+Shift+., katalog položek, `project-capabilities`, backend. (Skládání v `App.tsx` se změnilo podle bodu 1 Doladění: rám `editor-frame` se čtyřmi sloupci.)

## Hotovo, když

`npm test` a `npm run build` procházejí; každý panel má obě šířky; každá kategorie má ikonu i barvu z tokenu; písmo panelů 14px; světlý i tmavý režim čitelný. Ověření v běžící aplikaci (`http://127.0.0.1:8740`, Editor) na 1440×900.
