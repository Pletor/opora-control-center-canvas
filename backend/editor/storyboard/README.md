# Storyboard karty

Storyboard je soubor momentů (čas, popis, klíčový stav animace, komentář a šipky člověka) na kartě.
`validate_storyboard` hlídá meze a normalizuje; `StoryboardService` čte a atomicky zapisuje s revizí (CAS).
`brief_section` dává agentovi momenty včetně vět o šipkách do `node-brief`.
Pracovní autorita je append-only `storyboard_revisions`; původní JSON v
`canvas/workspaces/<wid>/storyboards/<nodeId>.json` se importuje a zůstává zachován.
Přijetí sdílí existující content proposals/manifests a accepted head.
Migrace a výslovný export pro návrat: `docs/storyboard-revize-a-navrat.md`.
Kontrakt: `docs/storyboard-karty.md`.
Router: `backend/api/editor/storyboard_routes.py`.
