# Slop audit (claude-design diagnostika, lokální workflow)

Surface: **COMMAND / INSPECT**. Skóre = počet aktivních „tells“ z 10 (méně je lépe).

## Před (base abdf852; snímky `evidence/design-before-*.png`)

| # | Tell | Stav | Kde |
|---|---|---|---|
| 1 | Tech gradient | ne | – |
| 2 | Generický indigo akcent | ne | zelený akcent, vlastní |
| 3 | Feature-tile grid | ne | – |
| 4 | Accent rail / dekorace místo hierarchie | **ano** | idle inspektor: „flow-rule“ řetěz boxů se šipkami; dekorativní glyfy v railu a stromu (◇ ¶ ✎ ⌘ ▧ ◈) |
| 5 | Unearned blur | ne | – |
| 6 | Monument stat | slabě | prázdné plátno: obří „＋“ a h1 25 px |
| 7 | Icon topper | **ano** | rail módů: velký glyf nad každým slovem |
| 8 | Center stack | **ano** | prázdný stav vystředěný uprostřed plátna („Prostor pro váš systém“) |
| 9 | Default type | slabě | Segoe UI bez rozhodnutí, 9–13 px, sedm velikostí bez škály |
| 10 | Wrong surface | **ano** | inspektor bez výběru = Decide/Learn copy („Celý systém. Jeden přesný uzel.“, marketingový řetěz procesu); dvě lišty (header 76 px + modebar) a trvalý levý strom = Operate-konzole místo Command/Inspect; formulářová stěna v detailu bez odkrývání |

**Skóre před: 4 (+2 slabé) / 10.** Příčina je kompoziční (8, 10), ostatní symptomy.

## Zásah podle diagnózy
- 8, 10 → **re-kompozice**: jedna lišta 48 px, rail, obsah-first, jeden kontextový inspektor (uzel: Obsah · Zadání · Práce; vrstva: Souvislosti · Deník; bez výběru: skutečný scope + nástroje módu). Levý strom odstraněn, navigace = drobeček + karty. Nastavení a git operace do jednoho menu.
- 4, 6, 7 → **odstranění dekorace**: žádný flow-rule, žádné glyfy, prázdný stav jako tichý odstavec vlevo nahoře.
- 9 → **typografie**: tokeny `--fs-0…5`, 13 px základ, 14 px v blokovém editoru, Segoe UI Variable Text jako záměrná lokální volba (bez CDN), mono jen pro identifikátory a stavový řádek.

## Po (snímky `evidence/design-desktop.png`, `design-text.png`, `design-mobile.png`)

| # | Tell | Stav |
|---|---|---|
| 1–3, 5–7 | | ne |
| 4 | | ne (aktivní mód v railu má vnitřní 2 px linku jako stav navigace, ne dekoraci karty) |
| 8 | | ne |
| 9 | | ne (zvolený systémový stack, škála) |
| 10 | | ne (Command/Inspect: obsah dominuje, kontext vpravo, zřídkavé akce v menu) |

**Skóre po: 0 / 10.** Zbytková rizika mimo tento řez: `<details>` zdrojového textu je otevřený kvůli přímé editaci a stávajícím testům (duplikuje bloky vizuálně); ProjectHome dostal jen tokeny, ne re-kompozici.
