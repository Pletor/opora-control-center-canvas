# Storyboard karty

Storyboard je soubor momentů (čas, popis, klíčový stav animace, komentář a šipky člověka) na kartě.
`validate_storyboard` hlídá meze a normalizuje; `StoryboardService` čte a atomicky zapisuje s revizí (CAS).
`brief_section` dává agentovi momenty včetně vět o šipkách do `node-brief`.
Soubor: `canvas/workspaces/<wid>/storyboards/<nodeId>.json`. Kontrakt: `docs/storyboard-karty.md`.
Router: `backend/api/editor/storyboard_routes.py`.
