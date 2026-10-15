# Pyramida: jak člověk předává záměr a jak se rozpadá do práce agentů

Člověk drží hlavní myšlenku toho, co se staví a jak to má fungovat. Nepíše robustní plány a neodklikává
dílky. Agenti potřebují dost informací, aby se rozkoukali, nevymýšleli a nezabloudili. Mezi tím je pyramida:
nahoře málo slov s velkou vahou, dole hodně konkrétních karet, a každá úroveň se **rozpadá** o jednu níž
volbou cesty, ne lineární čárou.

Stav: kontrakt (2026-10-15). Co z něj kód dnes provádí, je v §6. Měření, na kterém stojí: 208 karet v sedmi
projektech používá bloky s porty, cíl / mimo rozsah / akceptaci, pipeline etap, důkazy, podněty, kontroly a
`sourceRef`; fáze, kritéria, kroky, akce, scénář, fakta a design nepoužívá nikdo. To, co se nepoužívá, mizí.

## 1. Úrovně

| Úroveň | Prvek na plátně | Kdo píše | Co obsahuje (a nic víc) | Jak se rozpadá níž |
|---|---|---|---|---|
| **0 Projekt** | profil projektu (cíl, platforma), architektura domén | člověk | jedna věta cíle, platforma, domény (`www`, `app`, `admins`…) | domény → oblasti na kořenové vrstvě plátna |
| **1 Oblast** | `kind: "area"` na kořenové vrstvě | člověk | **záměr**: 2–5 vět, co tu má vzniknout a proč; barva | agent navrhne sektory (dávka `canvas-plan`), člověk potvrdí dávku jedním rozhodnutím |
| **2 Sektor** | `kind: "sector"` uvnitř oblasti | agent navrhne, člověk potvrdí | cíl, mimo rozsah, akceptace sektoru; brána (co musí platit, aby byl hotový); pravidla must/must_not | agent rozloží na karty (dávka), router každé kartě určí proces |
| **3 Karta** | `kind: "node"` ve vrstvě sektoru | agent | cíl, akceptace, bloky splnění s porty, `sourceRef`, kontroly; proces (kuličky) | relace na etapách, předávky po vazbách |
| **4 Blok** | `blocks[]` v kartě | agent | jedna ověřitelná podmínka, port = větev | `agent-output.blocks[].status` |

Pravidla pyramidy:

1. **Člověk píše jen na úrovních 0 a 1 a potvrzuje na úrovni 2.** Na kartě (3) a bloku (4) nic nevyplňuje;
   když chce něco změnit, změní záměr oblasti nebo cíl sektoru a nechá agenta přeložit to dolů.
2. **Každá úroveň má jeden důvod existence.** Oblast = téma (proč). Sektor = doručitelný celek s bránou (co
   znamená hotovo). Karta = jedna práce pro jednu relaci (jak). Blok = ověřitelná podmínka (ověřeno čím).
3. **Rozpad je volba cest, ne čára.** Sektor má zpravidla 3–9 karet; karty v sektoru se větví porty bloků
   a vazbami `next`. Lineární řetěz 20 karet je signál, že chybí sektor uprostřed.
4. **Rozhodnutí člověka se agregují nahoru.** Co čeká na člověka, se sbírá do jedné fronty (velín,
   „Čeká na tebe“) seřazené podle oblasti a sektoru; potvrzuje se dávka sektoru, ne karta po kartě.
   Podněty agentů (`ideas`) jsou jen počet na sektoru; k člověku se dostane až jejich **shrnutí** jako jedno
   rozhodnutí („v sektoru X se nasbíralo 14 podnětů, 3 mění záměr: …“), nikdy seznam.
5. **Agent dostává celou větev shora dolů.** `node-brief` nese `node.path` (jména předků), `context.area`
   (záměr oblasti), `graph.parent` (cíl, pravidla a rámec sektoru), `graph.areaMembers` a sousedy po vazbách.
   Nový model začíná od oblasti a čte směrem dolů; nic mimo tuhle větev nepotřebuje.
6. **Hotovo teče zdola nahoru.** Blok met → karta uzavřená (agent navrhne, člověk potvrdí dávku sektoru)
   → brána sektoru splněná → oblast hotová, když jsou hotové její sektory. Velín to ukazuje jako pruhy.

## 2. Co se na které úrovni ukazuje člověku

| Úroveň | Na plátně | Ve velínu (mód Velín) |
|---|---|---|
| Oblast | dashovaný rámeček s názvem a barvou; záměr v inspektoru | pásmo s názvem, záměrem na jeden řádek, pruhem stavů jejích sektorů |
| Sektor | zlatá karta: název, podstata, souhrn (hotovo / celkem, brána, blokuje) | dlaždice: název, účel, pruh stavů, počet karet / běží / selhalo / čeká, „Vstoupit“ |
| Karta | karta: název, podstata, **kuličky procesu + sloty dokladů + stavová věta** (`docs/proces-karty.md`), kontrolní pás, bloky s porty, fold Podrobnosti | řádek: název, stav práce, kuličky a sloty z dálky, počet podnětů |
| Fronta | — | „Čeká na tebe (N)“: ke schválení, uvízlo, otázka; seskupeno podle sektoru |

Mnemotechnika je stejná všude: zelená = hotovo, modrá = pracuje, jantar = čeká na člověka, červená = selhalo
nebo blokováno, šedá = čeká; kulička procesu: barva = kdo, výplň = jak dopadl, kroužek = kde proces stojí;
čtvereček dokladu: prázdný nedoloženo, poloviční deklarováno, plný doloženo, křížek selhalo.

## 3. Rozpad oblasti → sektory (další úroveň, kterou stavíme)

Vstup: oblast se záměrem (člověk). Výstup: dávka sektorů s cílem, akceptací a bránou, kterou člověk potvrdí
jedním rozhodnutím.

1. Člověk napíše záměr oblasti (inspektor oblasti, pole Účel; 2–5 vět). Záměr je text, ne formulář.
2. Agent v roli **rozkladač** (terminál se skillem, nebo asistent v okně) přečte `node-brief` libovolné karty
   v oblasti nebo rovnou `view` + záměr oblasti, mapu kódu (`GET /api/graphify/overview`) a navrhne
   `canvas-plan --dry-run`: 2–7 sektorů s `purpose`, `spec` (cíl, mimo rozsah, akceptace), bránou a
   pravidly. Každý sektor má větu „proč existuje“ odvozenou ze záměru.
3. Náhled dávky (digest) je jedno rozhodnutí člověka: potvrdit, nebo vrátit s poznámkou. Žádné odklikávání
   sektorů po jednom.
4. Po potvrzení se sektory objeví v oblasti (geometricky uvnitř rámečku). Rozpad sektoru na karty dělá
   další agent stejným způsobem (dávka → jedno rozhodnutí); router pak určí proces.

Kontrakt pro rozkladače je `.claude/skills/opora-control-center/references/canvas-plan.md` (dávka) a tento
dokument (co má sektor obsahovat). Laťka sektoru: cíl do 3 vět, akceptace jako seznam ověřitelných vět,
brána = jedna podmínka, pravidla jen ta, která se liší od projektu.

## 4. Co se nestaví

- Formuláře na kartě pro člověka (fáze, kritéria, kroky, akce, scénář, fakta, design): smazané, viz měření.
- Seznamy podnětů k proklikání: podněty zůstávají daty agentů; člověku se ukazuje počet a shrnutí.
- Automatické spouštění agentů z plátna: agenty spouští člověk v terminálu (nebo asistent na pokyn).

## 5. Kde to je v kódu

| Prvek | Kód |
|---|---|
| Oblast, členství podle polohy | `frontend/editor/canvas/area/`, `backend/canvas/areas.py` |
| Sektor, brána, souhrn | `frontend/editor/canvas/node-card/logic/sector-status.ts`, `backend/editor/agent_packet/sector_status.py` |
| Kuličky procesu, sloty dokladů, stavová věta | `frontend/editor/canvas/node-card/logic/card-process.ts`, `card-proofs.ts`, `card-state.ts`, `components/CardProcess.tsx`, `CardState.tsx`, `CardDetails.tsx` |
| Velín | `frontend/editor/control-tower/` (mód „Velín“ v Editoru, dříve „Mapa“) |
| Dávka rozpadu | `POST /api/canvas-plan` (`--dry-run` → digest → ostře), skill `references/canvas-plan.md` |
| Větev shora dolů pro agenta | `backend/editor/agent_packet/node_brief.py` (`node.path`, `context.area`, `graph.parent`) |

## 6. Stav provedení

| Krok | Stav 2026-10-15 |
|---|---|
| kuličky procesu na kartě | hotovo (c42a92f) |
| sloty dokladů Testy · Security · Review · Merge, stavová věta, fold Podrobnosti místo seznamu, editor důkazů pryč | hotovo (ranní směna 2026-10-15, `docs/proces-karty.md`) |
| smazání nepoužívaných formulářů karty | hotovo (7465a5a) |
| velín místo módu Mapa | hotovo (7465a5a) |
| záměr oblasti jako první věc v inspektoru a na rámečku, souhrn sektorů v oblasti, „Rozložit na sektory“ | hotovo (7465a5a) |
| shrnutí podnětů sektoru jako jedno rozhodnutí („Shrnout podněty“ v inspektoru sektoru, zadání pro agenta) | hotovo |
| předání karty agentovi jedním tlačítkem („Předat agentovi“ v inspektoru karty, s etapou na řadě) | hotovo |
| potvrzení návrhů uzavření přímo z fronty velína (jednotlivě i za sektor) | hotovo |
| fronta velína hlídá vrchol pyramidy: oblast bez záměru, sektor bez podstaty; „Zadání pro router“ u sektoru s nenasměrovanými kartami | hotovo (ce530ca) |
| role rozkladač ve skillu (`references/rozklad.md`) | hotovo (7465a5a) |
| sektor → karty: „Rozložit na karty“ v inspektoru sektoru, oddíl v rozklad.md | hotovo |
