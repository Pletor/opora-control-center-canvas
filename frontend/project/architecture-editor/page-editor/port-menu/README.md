# Nabídka vazby z portu

Dílek Editoru stránky podle `docs/zive-zobrazeni-a-knihovna.md` §4 (etapa M4). Klik nebo Enter na výstupním portu karty uzlu / sektoru (`map-card`) otevře u portu nabídku; tah z portu dál táhne vazbu (klik od tahu dělí práh pohybu `CLICK_SLOP`).

- **Hledání** podle názvu karty (bez háčků) a zároveň v Knihovně (`searchItems`).
- **Co po vazbě teče** – štítky Neurčeno / Navigace / Data / Příkaz / Událost. Karta na mapě druh toku na portu nemá, proto ho volí člověk tady; výchozí je „Neurčeno“.
- **Existující karty** – jen kompatibilní cíle podle téhož pravidla jako tah (`connectionProblem` v `../../logic/editor-model.ts`: ne sama sebe, komentář, oblast, už existující vazbu ani vazbu, která by uzavřela cyklus karet jako `backend/canvas/card_dag.py`). Klik uloží vazbu `next` se zvoleným `carries`.
- **Vytvořit a propojit** – položky Knihovny, jejichž první vstupní port přijme zvolený druh toku (u „Neurčeno“ stačí jakýkoli vstup). Klik pošle rodiči jeden plán `catalogPlan(item, placement, { nodeId: zdroj, side: "source" })`: karta i vazba (s `carries` vstupu nové karty) vzniknou jednou změnou grafu a jednou revizí. Nová karta stojí vpravo od zdroje (`newCardPosition` počítá s tělesy jako server, `canvas_plan_layout.py`, aby ji server neposunul).
- **Klávesnice** – fokus v hledání, šipky po položkách obou částí, Enter vybere, Escape zavře a vrátí fokus na port; klik mimo nabídku ji zavře, posun plátna také.
- **Umístění** – vpravo od výstupního portu, aby nepřekryla vstupy karty (ty jsou vlevo); bez místa pod kartou, případně nad ní, vždy uvnitř plochy plátna (`menuPosition`).

Soubory: `logic/port-menu.ts` (cíle, hledání, Knihovna podle druhu toku, šipky), `logic/port-menu-place.ts` (umístění nabídky a nové karty, klik vs. tah), testy vedle; `components/PortMenu.tsx` drží jen hledání, druh toku a aktivní položku; `styles/port-menu.css`. Stav otevření drží `ArchitectureCanvas`, ukládá `ArchitectureEditor` (`onConnect` s `carries`, `onInsert` s `link`). Chování je stejné pro všechny projekty.
