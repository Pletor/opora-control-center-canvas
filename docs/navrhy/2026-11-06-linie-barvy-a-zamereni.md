# Linie L6 – barvy stromu, gradientní spojnice, sbalení podstromu a zaměření na větev

Datum: 2026-11-06. Navazuje na L5 (`2026-11-06-linie-strom-vetvi.md`). Větev `feat/velin-linie-strom-barvy` (dítě
`feat/velin-linie-strom`), jen frontend `frontend/agi-pletor/dashboard/`.

## Proč

Člověk: „barvy u rodiče zvol na gradient, ať je vidět na šipkách i vnitřních puntíkách kam to směřuje, z čeho to plyne
… Když bude další dynamická větev (canvas 2), bude mít jinou barvu a stejný princip … bude 10 hlavních větví … Hlavní
větev dokáže zabalit pod sebe ostatní … Zobrazení editoru je hodně prázdného místa … pravý sloupec s MAIN zruš,
editor rozšiř na celou obrazovku … mohl si vybrat větev, na kterou se chce zaměřit.“

## 1. Barva větve (`logic/linie-color.ts`, čistá funkce, test vedle)

- Pevné: `main` `#4ade80`, `develop` `#60a5fa`, `items` + `items/*` `#c084fc`, `fix` `#f87171`, `experiment` `#a39cc4`.
- **Každý kořen `feat/<a>` má vlastní odstín**: `hue = hash(kořen) mod 360` (stabilní řetězcový hash, žádná náhoda
  mezi načteními; `feat/velin` i `feat/canvas-2` dostanou pokaždé tutéž barvu). Kořen = `hsl(hue 72% 52%)`.
- **Dítě dědí odstín a světlá/bledne s hloubkou**: hloubka `d` (kořen 2) → `hsl(hue, 72% − 10·(d−2) %, 52% + 9·(d−2) %)`,
  strop sytost 40 %, světlost 78 %. Žádná alfa (průhlednost se na tmavém podkladu ztrácela).
- `branchColor(branch, rows)` – kořen se najde řetězem `parent` z řádků boardu (`row.parent`), ne jménem; fallback
  pro neznámý rodič = develop. Vstup: `{ branch, type, depth, parent }[]`.
- Stejná funkce barví editor (`linie-board.ts` `rowColor`) i Git graf (`linie-graph.ts` `laneColor` – lane má
  `parent`, `depth`, `role`). Odstraní se `shade`, `ROW_COLOR.work`, `COLORS` v grafu.

## 2. Gradientní spojnice a kulička (`LinieBoard.tsx`, `LinieBall.tsx`, `linie-board.ts`)

- `LaidLink` nese `fromColor` (barva řádku, odkud vede) a `toColor` (barva řádku cíle). `planned` i `merged` se kreslí
  přes `<linearGradient gradientUnits="userSpaceOnUse" x1 y1 x2 y2>` od `fromColor` k `toColor`; hrot šipky a bod merge
  mají `toColor`. `follows` zůstává jednobarevný (barva řádku).
- `LaidBall` nese `color` (vlastní řádek) a `toColor` (řádek cíle z `planned`/`merged`, jinak `color`). `LinieBall`
  dostane `toColor` a kreslí **vnitřní puntík** v barvě cíle (r/3) u stavů `open`, `done`, `verify`; `blocked` zůstává
  červený střed, `merged` plná výplň vlastní barvou s tenkým prstencem `toColor`.
- Legenda: jedna položka „puntík = kam se začlení“.

## 3. Sbalení podstromu a zaměření (`DashboardLinie.tsx`, `linie-board.ts`)

- **Sbalení** řádku skryje všechny potomky (řetěz `parent`), ne jen jeho kuličky. Sbalený řádek nese chip „N větví ·
  M kuliček“. Ruční řádek si `collapsed` dál ukládá `PATCH /rows`; automatické a pevné řádky drží sbalení v
  `localStorage` klíč `pletor.linie.folded` (aplikace, ne projekt). Logika: `visibleRows(rows, folded)` čistá, test.
- **Zaměření**: klik na název řádku (ne dvojklik) nastaví `?branch=<větev>` (parametr už existuje jako `hint`);
  editor ukáže jen cestu ke kořeni (main, develop, předci – každý jako tenký řádek `ROW_THIN = 36 px` bez kuliček) a
  zaměřený podstrom v plné výšce. Nad editorem drobek „Zaměřeno: feat/velin-linie › zpět na vše“ (`✕` zruší).
  Logika: `focusRows(rows, branch)` čistá, test. Detail kuličky zaměření nemění.
- **Výška řádku dynamická**: řádek bez viditelných kuliček má `ROW_THIN`, s kuličkami `ROW_OPEN`, sbalený `ROW_FOLDED`.

## 4. Rozvržení (`DashboardLinie.tsx`, `pletor-dashboard-linie.css`, `pletor-dashboard-linie-editor.css`)

- Pravý sloupec s kartou MAIN **zrušit**. Její údaje (lokál/origin main, server HEAD, nasazeno, ochrana, tlačítko
  „Zapsat nasazené = HEAD serveru“) jdou do jedné řádky `pletor-dashboard__linie-status` pod lištou (text
  `view.*`, stejné `write("/deployed")`).
- `.pletor-dashboard__linie` je jeden sloupec na celou šířku; když je otevřený detail kuličky, Cesta nebo detail
  commitu, panel se otevře vpravo jako druhý sloupec 440 px (`--with-panel`), jinak nic.
- Časová osa i nadále vyplní šířku (`layoutBoard(board, span)`); osa začíná na prvním dni s kuličkou. Sloupec
  hlaviček 300 px zůstává.

## Ověření

`npx vitest run frontend/agi-pletor/dashboard`, `npm run build`, živě na náhledu: dva kořeny s různým odstínem (test
s fixture `feat/velin` + `feat/canvas-2`), gradient na plánované šipce L5 → feat/velin-linie, puntík v kuličce,
sbalení „Velín“ schová čtyři řádky, zaměření na `feat/velin-linie` ukáže jen její podstrom.

## Mimo rozsah

Backend se nemění. Ruční volba barvy kořene člověkem, uložení zaměření na server, Git graf sbalení.
