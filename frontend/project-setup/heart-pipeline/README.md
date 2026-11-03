Část **Pracovní workflow a pipeline srdce** na stránce projektu (`ProjectHome`, pod kartou Nastavení projektu).

- `components/HeartPipelineCard.tsx` – krátký popis srdce (LLM, které řídí projekt), živý souhrn a tlačítko „Otevřít canvas srdce“. Dostane hotový souhrn v props a klik hlásí `onOpen`; App otevře samostatnou obrazovku srdce (`screen=heart`, `project/heart-canvas/heart-screen/`).
- `logic/heart-pipeline.ts` (+ test) – souhrn z dat `useHeartData` (`project/heart-canvas/logic/`): workflow srdce, aktivní verze, počet běhů (strop výpisu 50 → „50+“) a prostoje z `/api/flow/stalls` jen z verzí tohoto workflow.
- Nic se tu neukládá; data načítá rodič `ProjectHome` stejným hookem jako plátno srdce.
