# agent-workspace

Pracovní prostor agenta u jedné karty (uzel, sektor i oblast): pět pojmenovaných polí —
rámec a směr, postup, co se nepovedlo, úspěšné opravy, předávka — kam si model vede mezipaměť
práce mezi revizemi. Kontrakt je `docs/karta-pro-agenty.md`, sekce „Pracovní prostor agenta“;
backend je `backend/editor/agent_memory/agent_workspace.py`.

- `logic/agent-workspace.ts` — čistý model: typy, pořadí a popisky sekcí (`SECTIONS`), prázdný
  prostor, které sekce se mezi dvěma verzemi liší (pro částečný zápis), odkaz na sekci
  (`opora://agent-workspace/<nodeId>#<sekce>`) a ořezání textu na limit.
- `logic/agent-overview.ts` — čistý model horního přehledu (`overviewModel`): cesta ke kartě, stav
  práce (kolik z pěti polí je napsaných a kdo psal naposled), nevyřízené položky komunikace
  (bez potvrzení, k upřesnění, otevřené otázky, stránkování), ověření (cíl, definice hotovo, počet
  mezer), další krok, bezpečnostní záruky a důvod zámku. Zdrojem je jediný načtený node-brief
  (`orientation`, `communication`, `loop.done`, `readOnly`) plus záznam prostoru — nic se nedomýšlí:
  chybějící záruka se hlásí jako „neuvedeno“, nedostupná komunikace nemá počty. Dál sem patří
  `safetyLine`, `briefReadOnlyFlags`, `sectionIndicator` a `sectionsOpenByDefault`.
- `logic/use-agent-workspace.ts` — hook nad `GET`/`POST /api/desktop-v3/agent-workspace`: načte
  prostor karty, ukládá jen změněné sekce pod CAS revizí, na revizní konflikt (409) prostor znovu
  načte a ukáže stejnou hlášku jako ostatní textové editory uzlu.
- `logic/agent-communication.ts` — čistá pravidla zpráv: payloady kontraktu, kontrola formuláře,
  slučování stránek, vlákna a jejich nevyřízenost, popisky a hlavička formuláře převzetí
  (`receiptHeadline` = chystaná akce · typ zprávy · výtah těla `messageExcerpt` · `shortDigest`).
- `logic/use-agent-communication.ts` — síťový stav panelu: načítá až po otevření, drží kurzory obou
  směrů, po každém zápisu ověřuje readback a příznakem `loaded` říká, jestli už panel má vlastní
  zprávy (do té doby jsou prázdné seznamy nevědomost, ne nula).
- `components/AgentCommunication.tsx` + `components/AgentMessageThread.tsx` — skládací panel
  komunikace. Formulář převzetí skládá rodič a vlákno mu drží místo přímo pod zprávou, které se
  týká (`receiptFormFor`, `receiptForm`): v hlavičce stojí akce, typ, výtah zprávy a její digest,
  vedle potvrzení je `Zrušit` a otevřený je vždy nejvýš jeden. Úspěšné převzetí i odeslání hlásí
  rodiči přes `onChanged`; zavřená hlavička ukáže počet z briefu (`pendingHint`), dokud panel
  nenačetl vlastní zprávy.
- `components/AgentWorkspace.tsx` — rodič záložky Agenti: drží `useAgentWorkspace` i
  `useAgentOrientation` (node-brief se načte právě jednou) a skládá pořadí hlavička → přehled →
  start pro agenta → komunikace → pět polí. Komunikaci dává `pendingHint` z briefu a
  `onChanged={orientation.reload}`, takže se počty v přehledu obnoví po zápisu, ne pollingem. Draft
  je lokální a ukládá se při opuštění pole (blur). Umí dvě rozložení: `layout="stack"` (výchozí) je
  dnešní sloupec do inspektoru, `layout="segments"` rozprostře tytéž celky po ploše Agenti — tam
  rozbalení, odkazy z přehledu i „Rozbalit vše / Sbalit vše“ přicházejí shora v props (`open`,
  `onToggle`, `onGoTo`, `onExpandAll`, `onCollapseAll`) a `onMemoryDefaults` hlásí desce, která pole
  paměti už něco nesou. Roli karty dostává v `agentRole` a změnu hlásí `onRoleChange`; segment
  Paměť role (`memory/`) montuje jen v rozložení `segments`.
- `components/AgentMemorySections.tsx` — pět polí paměti. Ve `stack` je to pět složených sekcí
  (`<details>`) s popiskem a poznámkou „prázdné“ / „N znaků“, v `segments` pět stejně širokých
  pojmenovaných sloupců. Dílek nic neukládá: text dostává v props a změnu i blur hlásí nahoru; odkaz
  na sekci kopíruje tlačítko vedle nápovědy.
- `components/AgentOverview.tsx` — přehled nahoře: cesta ke kartě a tři dlaždice Práce /
  Komunikace / Ověření s počty nevyřízených položek, pod nimi jedna věta „další krok“, věta o
  zárukách (aplikace model nespouští, převzetí nepotvrzuje automaticky, vlastnictví nepřevádí) a
  konkrétní důvod zámku (uzavřená karta vs. main jen ke čtení). Dílek nic nenačítá; brief i záznam
  prostoru dostává v props a jen je mapuje přes `overviewModel`. Když rodič pošle `onGoTo`, stanou
  se z počtů (Bez potvrzení, K upřesnění, Otevřené otázky, Mezery) a z dlaždice Práce odkazy na
  kotvy segmentů, které se cestou rozbalí; bez `onGoTo` zůstává pás prostým textem.
- `memory/` — segment **Paměť role** (OpenViking): co role umí napříč projekty, co ví o tomhle
  projektu a co si výslovně půjčila od jiné role. Kreslí se jen na ploše Agenti; v inspektoru
  (`layout="stack"`) se nemontuje vůbec. Roli karty (`agentRole`) panel neukládá — hlásí ji nahoru
  přes `onRoleChange` a ukládá ji deska obyčejnou mutací stavu Desktop v3. Vlastní `README.md`.
- `segments/` — plocha podzáložky Text → Agenti: lišta karet vlevo, pojmenované segmenty vpravo,
  rozbalení uložené jednou pro celou aplikaci. Vlastní `README.md`.
- `styles/agent-workspace.css`, `styles/agent-overview.css`, `styles/agent-communication.css` —
  BEM bloky `agent-workspace`, `agent-overview` a `agent-communication`.

Co tenhle dílek neukládá: zadání karty (`goal`/`non_goals`/`acceptance` — to je `NodeSpecEditor`
v `assignment/`), obsah uzlu (`NodeTextEditor` v `content/`), zprávy na vazbách (`EdgeReportPanel`
v `canvas/edge-report/`) ani uzavření karty (`DoneControl` v `done/`). Prostor patří modelu — nic
v něm není příkaz ani zadání; člověk do něj smí psát, ale neřídí tím agenta.
