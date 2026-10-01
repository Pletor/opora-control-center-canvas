Jedna lineární ikonová sada pro celou aplikaci. Kontrakt: `docs/panely-editoru.md`, „Doladění po první implementaci“, bod 4 (Ikony) — Unicode glyfy (▦ ¶ ⌘ ⋮⋮ ⌕) se ruší, kreslí se SVG.

**Dílek**

- `components/Icon.tsx` — `<Icon name="workflow" size={20} />`. Vykreslí `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">` s jedním `<path d>`. Props: `name` (jméno ze sady), `size` 16 | 20 | 24 (výchozí 20), `className` (třída okolí — barva a poloha), `label`. Bez `label` je ikona ozdoba vedle popisku a odečítač obrazovky ji přeskočí (`aria-hidden`); s `label` se z ní stane obrázek se jménem (`role="img"` + `aria-label`) — to je případ tlačítka bez textu. Barvu si dílek nevolí, kreslí `currentColor`: obarví ho to, kam je vložený (žeton kategorie `--c`, tichý řádek `--ink-muted`, aktivní žeton `--surface`).
- Styl si dílek načítá sám (`import "@/ui-kit/icon/styles/icon.css"` v komponentě, jako většina dílků v repozitáři), takže ikona funguje všude, kde se importuje, a nikdo na to nemusí myslet v `App.tsx`.

**Sada**

`logic/icon-paths.ts` je tabulka `jméno → d` na plátně 24×24 (`ICON_PATHS`, typ `IconName`) plus `iconPath(name)`, který neznámému jménu vrátí `""` — dílek pak nenakreslí nic a rozhraní se kvůli ikoně nerozbije. Test vedle (`icon-paths.test.ts`, běží `npm test`) hlídá, že každá ikona má neprázdnou cestu, že cesta začíná `M` a že neznámé jméno vrací `""`.

Tvary jsou obkreslené ze sady **Lucide (licence ISC)** a vložené **ručně jen pro ikony, které rozhraní opravdu používá** — žádný balík navíc, žádné ikonové písmo. Víc podcest v jedné `d` je v pořádku; kruhy a obdélníky Lucide jsou přepsané na oblouky a rohy, aby se všechno vešlo do jediného `<path>`.

Sada dnes (40 jmen):

| Skupina | Jména |
|---|---|
| Módy plátna a Knihovna | `layout-grid`, `type`, `pencil`, `map`, `bot`, `library` |
| Kategorie bloků | `component`, `function-square`, `palette`, `server`, `database`, `refresh-cw`, `shield`, `cloud`, `check-circle` |
| Kategorie postupů | `workflow`, `link`, `scale`, `terminal`, `sparkles`, `users` |
| Sekce zadání karty | `target`, `cpu`, `repeat`, `arrow-left-right`, `folder` |
| Stav a směr v zadání karty | `circle`, `check`, `arrow-up`, `arrow-left`, `arrow-right` |
| Ovládání panelů | `search`, `chevron-left`, `chevron-right`, `panel-left-close`, `panel-left-open`, `panel-right-close`, `panel-right-open`, `grip-vertical`, `home` |

Některá jména slouží dvěma pánům a je to záměr, ne nedopatření: `layout-grid` je mód Struktura i sektor ve stromu vrstev, `component` kategorie Komponenty i uzel, `map` mód Mapa i oblast. Ikona kreslí věc, ne místo — stejná věc má mít všude stejný tvar.

**Kdo mapuje id na ikonu**

Sada ví jen, jak se která ikona kreslí. Mapování „id módu / kategorie / druhu → jméno ikony“ zůstává v `logic/` toho panelu, který ikonu ukazuje: `layout/mode-rail/logic/mode-rail.ts` (`modeIcon`, `LIBRARY_ICON`), `layout/agent-navbar/logic/agent-navbar.ts` (`categoryIcon`), `layout/library-navbar/logic/library-navbar.ts` (`categoryIcon`, `layerKindIcon`). Nová ikona = nový řádek v `IconName` a cesta v `ICON_PATHS`; mapování se sem nikdy nestěhuje.

**Styl**

`styles/icon.css`, blok `icon`, varianty `icon--16`, `icon--20`, `icon--24`. Ikona je součástí řádku (`display: inline-block`, `vertical-align: middle`), nikdy se nesmrskne (`flex: none`) a nemá vlastní barvu ani okraj — to všechno patří místu, kam je vložená.
