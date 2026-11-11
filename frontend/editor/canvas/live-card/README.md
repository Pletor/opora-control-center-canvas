# Živá karta (detail karty na 3/4)

Detail karty Editoru uprostřed obrazovky (`min(76vw, 1240px)` × `min(88vh, 920px)`), plátno zůstává ztlumené za ním.
Líc pro člověka, rub pro agenty; přepínač „Pro člověka | Pro agenty“ vedle ✕ kartu otočí. Kontrakt: sekce
„K1: kontrakt živé karty“ v `docs/navrhy/2026-11-11-platno-3-folie.md`.

- Otevírá se přes `openCardDrawer(nodeId)` **bez záložky** (dvojklik na kartu, Velín, OporaHub, živý pás); URL `?ohCard=<id>`.
  Se záložkou (`openCardDrawer(id, tab)`, URL `&ohTab=`) se otevře rovnou pracovní panel `hub/oporahub-card-drawer`.
  Tlačítko **Pracovní panel** (patička líce i rub) přepne na drawer se záložkami spec/steps/lens/run/review/history.
- Rodič `components/LiveCard.tsx` drží stranu a data z `logic/use-live-card.ts`: `GET /api/oporahub/live-card`,
  živý deník ze sdíleného toku `eventsClient` (události karty novější než první snímek, nahoru do `recent`, ≤ 30)
  a na rubu `GET /api/desktop-v3/node-brief?…&layer=souhrn|tvar` (JSON se ukáže tak, jak přijde).
- Dílky jen props a callbacky: `CardHead` (kruh, drobečky, štítky, počitadla, přepínač, ✕), `HumanSide` skládá
  `Teleports`, `TruthsGrid` (mirror s `available:false` = šedá „staví se F1“; budoucnost jen s `available:true` kreslí `FutureTruth`: verdikt, větev → cíl, konflikty ✕, dopady a překryvy, změněné soubory v `title`; měřené zrcadlo kreslí `MirrorTruth`: shoda fixou + soubor:řádek, chybí ○, navíc červeně, pruh shoda/(shoda+chybí), plná cesta v `title`), `FlowOutput`, `LinieTrends`,
  `RunLog` (dráhy + deník; dráha podle druhu, pak aktéra `actorView`: `worker.message` srdce, `tool.use`/`turn.*`/`worker.*`
  dělník, `card.signal` hlídač nebo trigger), `DecisionsChildren`; `CardFoot` (další krok, zásah srdce, Zeptat se srdce, náhled,
  Obnovit, Pracovní panel, **Předat do Kanceláře** jen bez `linie`: formulář Velína `LinieWorkForm` předvyplněný
  `logic/card-work.ts`, `POST /api/pletor/linie/work` s `cardId`, chyba v patičce, po založení obnova karty); `AgentSide` + `JsonBlock` (adresa, lease, #souhrn/#tvar, čtení, zápis, spouštěče,
  syrový proud, nástroje).
- Sekce s `null` nebo prázdnými daty se nevykreslí. Čistá logika: `logic/live-card-view.ts` (stavy, pruhy pravd,
  vazby, sparkline, dráhy, převod události), `logic/json-tokens.ts` (zvýraznění JSON bez innerHTML), typy a parser
  `logic/live-card-types.ts`, fixtura `logic/live-card-fixture.ts`.
- Escape, klik mimo i ✕ zavřou kartu a vrátí fokus tam, odkud byla otevřena (`use-drawer-focus`).
