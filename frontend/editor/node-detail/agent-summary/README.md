# agent-summary

Souhrn práce agentů nahoře na stránce módu Text (podzáložka Uživatel): jedna tabulka jen pro
**rozbalené** kapitoly — kdo na kartě pracuje, kolik paměti má, co čeká na člověka, jestli karta ví,
kam jde, a co dál. Kontrakt je `docs/souhrn-prace-agentu.md`. Skládá ho `content/TextWorkspace`, který
drží filtr, řazení, hover a skok na kapitolu; dílky odsud používá i hlavička kapitoly (`TextChapter`).

- `logic/agent-summary.ts` — čistý model: `summaryRows` (pořadí dětí, jen rozbalené, bez komentářů),
  `chapterWork` (levný souhrn, jinak práce z briefu), `workStateOf`, `pendingCount` (nedostupná
  komunikace = 0), `isRowLocked`, `SUMMARY_FILTERS` + `filterRows`, `nextRank` + stabilní `sortRows`
  (0 chybí cíl → 1 chybí definice hotovo → 2 mezery → 3 čeká na člověka → 4 ostatní i bez briefu →
  5 zamčené), `relativeTime` (české tvary, neplatné datum „–“), `actorLabel`, `nextActionIcon`,
  `memoryTitle`, `gapsLabel`, `summaryHeadline`.
- `logic/chapter-queue.ts` — pravidla fronty briefů bez Reactu: `worksFrom` (čtení odpovědi
  souhrnu), `nextStale`/`staleIds` (kdo je na řadě v aktuální generaci obnovy), `markLoading` (při
  obnově zůstává starý přehled vidět).
- `logic/use-chapter-overviews.ts` — síť: `fetchAgentWorkspaceSummaries` při připojení, změně rozsahu,
  `refresh()` a změně `refreshKey` (sdružené po 1500 ms); briefy (`fetchNodeBrief` → `overviewModel`)
  jen pro rozbalené karty a **jeden dotaz najednou**, protože brief drží zámek plátna. Sbalená karta
  si záznam nechá, ale znovu se nenačítá. Odpověď ze starého rozsahu nebo po odpojení se zahodí.
- `logic/use-now.ts` — minutové hodiny pro relativní časy; čas rozdává rodič.
- `components/AgentSummary.tsx` — rodič: hlavička („N rozbalených karet · M čeká na tebe“, řazení,
  Obnovit), řada filtrů, tabulka, legenda, prázdný stav a „Filtru nic neodpovídá.“
- `components/AgentSummaryRow.tsx` — řádek: Karta (odkaz na kapitolu) · Stav · Paměť · Komunikace ·
  Ověření · Další krok · Změna · zámek. Bez briefu jsou komunikace, ověření a další krok „–“.
- `components/WorkChip.tsx`, `MemoryDots.tsx`, `CommsChips.tsx`, `AgentSummaryLegend.tsx` — žetony a
  legenda; nic nenačítají.
- `styles/agent-summary.css` — BEM blok `agent-summary`; mřížka osmi sloupců, pod 964 px šířky desky
  (`@container`) se sloupec Změna přesune pod název karty.

Co dílek nedělá: nic neukládá (ani filtr a řazení — to je stav pohledu v `TextWorkspace`), neotevírá
inspektor a nečte `sourceKind`. Zámek a uzavření karty dostává hotové (`isClosed`, `readOnlyReason`).
