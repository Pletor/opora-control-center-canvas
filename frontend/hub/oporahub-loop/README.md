# Přehled: smyčka plán → kód → plán

Výchozí pohled OporaHubu. `LoopOverview` skládá `TopStrip` (přijatá hlava, drift, mix rizika, nejvýše 3 rozhodnutí), smyčku deseti etap (`StageNode` + `LoopConnector`, poloha v „hadovi“ přichází z `loop-model.ts` přes `--oh-row`/`--oh-col`) a pás známých mezer. Data jsou jen z dokumentu agent-state; klik na etapu nebo rozhodnutí otevře existující detail. Na úzkém displeji se had rozvine do jednoho sloupce.
