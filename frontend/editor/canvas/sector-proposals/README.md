# sector-proposals

Hromadné potvrzení návrhů uzavření v sektoru: čip **Ke schválení: N** v hlavě vrstvy (lišta plátna
`board-bar`), když je člověk uvnitř sektoru. Vráceno po PR #30, které tlačítko smazalo spolu se starou
kartou a Velínem; audit sirotků (#45, položka 4) našel 37 lidských volání `POST /api/desktop-v3/confirm-proposals`.

- `logic/sector-proposals.ts`: `sectorProposals(graph, state, sectorId, index?)` vrátí čekající návrhy
  agenta pod sektorem (do hloubky, přes `proposalsIn`) s připraveností důkazů (`evidenceReadiness`).
  Hromadně (`batchIds`) jde jen karta s hotovými důkazy bez N/A, nejvýš 200 v jednom zápisu; ostatní
  člověk potvrzuje jednotlivě na kartě. `confirmSector(...)` přečte revizi těsně před zápisem a pošle jeden
  `POST /api/desktop-v3/confirm-proposals` `{project, workspace, sectorId, nodeIds, expectedRevision}`.
- `components/SectorProposals.tsx`: bez návrhů vypnuté tlačítko „✓ Potvrdit návrhy (0)“; s návrhy čip, který
  rozbalí seznam a tlačítko „✓ Potvrdit návrhy (M)“ (dva kroky, potvrzení je nevratné). Chyba serveru zůstane
  v panelu (`role="alert"`) a čip zjantaroví. Ukládá rodič: Board volá `onConfirmSector(sectorId, ids)`,
  App výsledek aplikuje přes `desktop.apply`.

Proč ne ve Velínu, kde tlačítko bylo dřív: Velín (`editor/control-tower`) teď stojí na agent-state a vlastní
ho jiná práce. Hlava sektoru na plátně je druhé místo, kde tlačítko žilo do #30, a člověk tu návrhy vidí
na kartách hned pod ním.
