# Plátno srdce (plátno 1)

Plátno 1 na samostatné obrazovce srdce (`screen=heart`, `project/heart-screen/`, vstup „Otevřít canvas srdce“ na stránce projektu; kontrakt `docs/navrhy/2026-11-03-novy-zaklad.md` §3.5). `HeartCanvas` vybere workflow `kind=heart` projektu (vlastní má přednost před sdíleným „Srdce v1“) a ukáže graf jeho verze ve sdíleném editoru `shared/flow-editor`.

- **Editor:** zobrazená verze (výchozí aktivní) a rozdíl proti jiné verzi (výchozí rodič; přidané, odebrané a změněné uzly a vazby). Úprava grafu je jen lokální, dokud ji člověk neuloží jako **nový draft** (`POST /api/flow/workflows/{id}/versions`); draft jde navrhnout ke evalu jako **kandidát** (`POST /api/flow/versions/{id}/candidate`). Aktivní verzi plátno nikdy nepřepíná.
- **Běhy:** seznam běhů a prostojů s důvodem (`run-list/`), vybraný běh na své verzi jen ke čtení se stavy uzlů a cenou na hranách a spodní log událostí (`run-log/`) synchronizovaný s plátnem (klik na událost vybere uzel, vybraný uzel zvýrazní své události).
- `logic/heart-api.ts` (+ test) — adresy a čtení `/api/flow/*`, výběr workflow a verze. `use-heart-data.ts` — workflow, verze, registr, běhy a prostoje (běhy a prostoje po 5 s). `use-run-detail.ts` — detail a log běhu (neukončený po 3 s).
- `version-bar/` — štítky verzí, srovnání, akce draft / kandidát.
- `useHeartData` používá i souhrn srdce na stránce projektu (`project-setup/heart-pipeline/`).

Jedno rozhraní pro všechny projekty: plátno nečte druh projektu; liší se jen tím, jaké workflow srdce projekt má.
