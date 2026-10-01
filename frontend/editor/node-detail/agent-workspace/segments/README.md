# agent-workspace/segments

Plocha podzáložky **Text → Agenti**: místo jednoho úzkého sloupce, ve kterém se pracovní prostor
opakoval pro vrstvu i pro každé dítě, stojí vlevo lišta karet a vpravo pojmenované segmenty té
jediné karty, kterou člověk vybral. Obsah segmentů se nemění — je to týž `AgentWorkspace`, jen
rozprostřený (`layout="segments"`). Kontrakt je `docs/karta-pro-agenty.md`, pohled popisuje
`docs/agent-handoff-workspace.md`, sekce „Co uživatel vidí v Text → Agenti“.

- `logic/agent-segments.ts` — čistý model plochy: devět segmentů v pevném pořadí
  (`overview | orientation | communication | memory | frame | log | failures | fixes | handoff`)
  s titulkem, jednou větou „k čemu to je / kdo sem píše“, oblastí (`overview` = pás, `top` = horní
  trojice, `memory` = pět polí paměti karty) a výchozí polohou `startsOpen`; segment, který se do
  poloviny řádku nevejde, má `wide`. Kotva segmentu `segmentId(nodeId, id)` = `agent-seg-<nodeId>-<id>`;
  výchozí rozbalení (`defaultOpen`), hromadné `expandAll`/`collapseAll` a čtení, zápis a složení
  uložené preference (`parseSegmentPrefs`, `readSegmentPrefs`, `writeSegmentPrefs`, `mergeOpen`).
  Úložiště se předává v argumentu, modul nikdy nesahá na globální `localStorage`; test leží vedle.
  Pozor na dvojí význam slova paměť: oblast `memory` je pět polí karty, segment `memory` je
  **Paměť role** (OpenViking) a ten je napoprvé zavřený, protože sahá na cizí službu.
- `components/AgentSegmentsBoard.tsx` — deska: drží vybranou kartu, rozbalení segmentů a stav
  Desktop v3 (`useDesktopState`) kvůli roli karty, napravo montuje **právě jeden** `AgentWorkspace`
  s `key={nodeId}`. Nevybraná karta se nenačítá, takže vrstva s deseti dětmi nedělá deset dotazů;
  drafty a ukládání zůstávají uvnitř prostoru beze změny. Roli uzlu (`agentRole`) ukládá deska
  obyčejnou mutací stavu (`setAgentRole` v `../memory/logic/agent-role.ts`), na main jen ke čtení
  callback vůbec nepošle.
- `components/AgentCardRail.tsx` — lišta karet: vrstva a její děti, vybraná svítí, u dítěte zůstává
  „Zanořit“ ve stejné roli jako v dokumentu.
- `components/AgentSegmentsLayout.tsx` — pořadí čtyř horních segmentů (Přehled, Start pro agenta,
  Komunikace, Paměť role) a za nimi hotová pole paměti karty. Dostává je v props jako hotové kusy;
  Paměť role je volitelná (`roleMemory`), takže v inspektoru se nekreslí vůbec.
- `components/AgentSegment.tsx` — obecný rám jednoho segmentu: kotva s ID karty, titulek, popisek a
  přepínač Sbalit/Rozbalit. Sbalený segment se neodmontuje, jen skryje (`hidden`), takže rozepsaná
  zpráva ani otevřené vlákno komunikace nezmizí.
- `styles/agent-segments.css` — BEM blok `agent-segments`: `__rail`, `__rail-item--selected`,
  `__grid`, `__segment--open`, `__segment--wide`, `__segment-head`, `__caption`.

Co tenhle dílek nedělá: nenačítá ani neukládá obsah karty (to je `useAgentWorkspace` a
`useAgentCommunication`), nerozhoduje o uzavření karty (`isClosed` dostává v props) a nic neukládá
per projekt — rozbalení je vzhled, a ten se podle `docs/pravidla-struktury.md` ukládá jednou pro
celou aplikaci pod klíčem `opora:agent-segments:v1`.
