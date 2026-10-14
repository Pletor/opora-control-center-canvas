Velín (mód `map` v Editoru, v liště „Velín“): jedna obrazovka, ze které člověk řídí celý projekt. Ukazuje
pyramidu plátna — **oblast** (`kind: "area"` na kořenové vrstvě) → **sektor** (`kind: "sector"`, člen oblasti
podle polohy, `areaOf`) → **karty** (`kind: "node"` s `parentId = sektor`) — se stavem procesu a jedinou
frontou „Čeká na tebe“. Nic se tu nevyplňuje ani neukládá; klik otevře kartu (`onOpenNode`) nebo vstoupí do
vrstvy sektoru (`onEnterLayer`) a App přepne zpět do Struktury.

`logic/tower-model.ts` (testováno) je čistý model bez Reactu ve dvou fázích. `towerStructure(graph)` je jen
geometrie a hierarchie: členství v oblasti spočítá jednou pro každý kořenový sektor a kartu (`areaOf`),
oblasti a sektory řadí podle y, x, strom sektorů staví celý (ochrana `seen` proti cyklu) a uzly
nedosažitelné z kořene (rodič neexistuje, cyklus) dá mezi `loose` / `looseCards` místo zahození.
`towerFrom(structure, state, work, workState)` nad ní doplní stav karet: stav práce z `work-overview`
(bez něj `idle` a `statusKnown: false`; uzavřená `done`), návrh uzavření agentem (`proposed`), proces
`processView(stages)`, otázky agenta (`waiting`) a počet otevřených podnětů. `Tower.workState` je
`loading` / `unavailable` / `loaded`. Součty (`Counts`) jdou zdola nahoru přes celou hloubku; koše
`closed` / `proposed` / `failed` / `waitingHuman` / `running` se nepřekrývají (`cardBucket`), takže z nich
`countSegments` staví pruh stavů beze zbytku; `unrouted` je navíc. Fronta (`inbox`) je celá, seřazená:
ke schválení, uvízlé procesy, otázky; `inboxPage` z ní dá filtr druhu a prvních N, `inboxKinds` počty pro
čipy, `inboxCardCount` počet dotčených karet a `groupInbox` skupiny podle id sektoru, mimo sektor podle id
oblasti. `contentLabel` je popisek rozbalení („Obsah: 3 karty · 1 podsektor“). `buildTower` spojí obě fáze.

`components/ControlTower.tsx` je rodič: drží jen `useWorkOverview`, rozbalení sektorů a filtr / stránkování fronty (po 50) a memoizuje strukturu podle `graph` zvlášť od stavu; skládá dílky
`TowerSummary` (horní pás s pruhem a čísly), `TowerArea` (pásmo oblasti s pruhem barvy rámečku z plátna),
`TowerSector` (dlaždice sektoru, rozbalení, „Vstoupit“; kreslí nejvýš `MAX_SECTOR_DEPTH` úrovní), `TowerCardRow` (řádek karty s čipem stavu a
kuličkami `CardProcess`), `TowerInbox` (fronta s čipy druhu, „Zobrazit dalších“ a hlášením, když stav práce chybí) a `TowerBar` (tenký pruh stavů; šířku nese jen CSS proměnná
`--w`). Styl v `styles/control-tower.css` (BEM, bloky `control-tower`, `tower-bar`, `tower-summary`,
`tower-inbox`, `tower-area`, `tower-sector`, `tower-card`); pod 1000 px šířky jde fronta nad pyramidu.

Přímé akce fronty: `ControlTower` bere nepovinné `onConfirmProposal(nodeId)` a `onConfirmSector(sectorId,
ids)` — App mu dává tytéž handlery jako plátnu (`confirmProposalNow`, `confirmSectorNow`). U položky „ke
schválení“ je `ConfirmButton` „Potvrdit“, ve skupině sektoru se dvěma a víc návrhy „Potvrdit vše v sektoru
(N)“; uvízlé procesy a otázky mají jen „Otevřít“, protože rozhodnutí potřebuje kontext karty. Potvrzení je
nevratné, proto bez `confirm()` dialogu dvojí klik: `logic/inbox-actions.ts` (testováno) drží automat
`confirmStep` (idle → armed na `ARM_MS` = 4 s → busy → idle / error, `tick` po vypršení vrací do klidu) a
`proposalsBySector` (sektor → id návrhů z celé fronty, ne jen viditelné stránky). Úspěch nic nepřekresluje
sám: položka zmizí, až přijde nový stav plátna.
