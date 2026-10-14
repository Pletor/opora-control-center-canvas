Velín (mód `map` v Editoru, v liště „Velín“): jedna obrazovka, ze které člověk řídí celý projekt. Ukazuje
pyramidu plátna — **oblast** (`kind: "area"` na kořenové vrstvě) → **sektor** (`kind: "sector"`, člen oblasti
podle polohy, `areaOf`) → **karty** (`kind: "node"` s `parentId = sektor`) — se stavem procesu a jedinou
frontou „Čeká na tebe“. Nic se tu nevyplňuje ani neukládá; klik otevře kartu (`onOpenNode`) nebo vstoupí do
vrstvy sektoru (`onEnterLayer`) a App přepne zpět do Struktury.

`logic/tower-model.ts` (testováno) je čistý model bez Reactu ve dvou fázích. Hierarchie je obecná:
vnitřní vrstvu může mít sektor i karta (dvojklik na plátně = do hloubky). Karta s dětmi je **kontejner**
a kreslí se jako dlaždice (`kind: "card"`, stav karty v `card`); prostá karta je řádek. `towerStructure(graph)`
je jen geometrie a hierarchie: pro každou vrstvu (kořen, sektor, kontejner) seskupí její sektory a karty
podle oblastí **té vrstvy** (`areaOf` jednou pro každý uzel, jen proti oblastem vrstvy), strom staví celý
(ochrana `seen` proti cyklu) a uzly nedosažitelné z kořene (rodič neexistuje, cyklus) dá na kořen mimo
oblast místo zahození. Každý sektor a karta z grafu je v pyramidě přesně jednou (`towerIds`; ověřeno i na
živém grafu Ample: 152 uzlů, 143 karet). `towerFrom(structure, state, work, workState)` nad ní doplní stav
karet: stav práce z `work-overview` (bez něj `idle` a `statusKnown: false`; uzavřená `done`), návrh
uzavření agentem (`proposed`), proces `processView(stages)`, otázky agenta (`waiting`) a počet otevřených
podnětů. `Tower.workState` je `loading` / `unavailable` / `loaded`. Součty (`Counts`) jdou zdola nahoru přes
celou hloubku (u kontejneru včetně karty samotné); koše `closed` / `proposed` / `failed` / `waitingHuman` /
`running` se nepřekrývají (`cardBucket`), takže z nich `countSegments` staví pruh stavů beze zbytku;
`unrouted` je navíc. Fronta (`inbox`) je celá, seřazená: ke schválení, uvízlé procesy, otázky; `inboxPage`
z ní dá filtr druhu a prvních N, `inboxKinds` počty pro čipy, `inboxCardCount` počet dotčených karet a
`groupInbox` skupiny podle id nejbližší dlaždice (a oblasti v její vrstvě). `layerSize` a `contentLabel`
dávají popisek rozbalení („Obsah: 3 karty · 1 podsektor · 2 oblasti“). `looseArea` je kořenové pásmo mimo
oblast („Kořen plátna“, když kořen oblasti nemá). `buildTower` spojí obě fáze.

`components/ControlTower.tsx` je rodič: drží jen `useWorkOverview`, rozbalení sektorů a filtr / stránkování fronty (po 50) a memoizuje strukturu podle `graph` zvlášť od stavu; skládá dílky
`TowerSummary` (horní pás s pruhem a čísly), `TowerArea` (pásmo oblasti s pruhem barvy rámečku z plátna, na kořeni i uvnitř dlaždice), `TowerLayer` (obsah vrstvy v pořadí oblasti → sektory → karty → kontejnery; dlaždice hlouběji než `MAX_SECTOR_DEPTH` nekreslí, jen karty),
`TowerSector` (dlaždice sektoru nebo kontejnerové karty se štítkem „karta s vrstvou“, rozbalení, „Vstoupit“, u kontejneru „Otevřít kartu“), `TowerCardRow` (řádek karty s čipem stavu a
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
