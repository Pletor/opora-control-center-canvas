# Provenance a meze návodu

## Autorita

Návod vychází z přečteného zdrojového kódu OPORA Control Center, nikoli pouze
z referenčních obrázků. Živý server nemusí používat tutéž revizi jako checkout:
frontend může být aktualizován bez restartu backendu. `/api/build-identity`
zachycuje start backendu; zvlášť porovnávej servírovaný index a zdrojové soubory.
Současné runtime schopnosti mají přednost před předpokladem v tomto manuálu.

Cesty níže jsou relativní vůči repozitáři aplikace, nikoli vůči skillu.
Nečti všechny soubory; vezmi jen kontrakt právě řešené operace.

| Oblast | Primární zdroj |
|---|---|
| Přepínání prostředí, URL a vytváření uzlů | `frontend/app/components/App.tsx` |
| Projekt/workspace, menu | `frontend/layout/top-bar/components/TopBar.tsx` |
| Módy plátna | `frontend/layout/mode-rail/components/ModeRail.tsx`, `frontend/shared/surface-settings/logic/workspace-settings.ts` |
| Inspektor uzlu | `frontend/editor/node-detail/components/NodePanel.tsx` |
| Text a zadání, revize | `frontend/editor/node-detail/content/components/NodeTextEditor.tsx`, `frontend/editor/node-detail/assignment/components/NodeSpecEditor.tsx` |
| Reference a zakázané cesty | `frontend/shared/selection/logic/workspace-selection.ts` |
| Vstup práce s AI (dok Podklady pro agenta) | `frontend/app/components/App.tsx` (`agent-packet-dock`), `frontend/editor/llm-control/agent-packet/components/AgentPacketPanel.tsx` |
| Podklady pro agenta: náhled, snímek, export | `frontend/editor/llm-control/agent-packet/components/AgentPacketPanel.tsx` |
| Klientské API a readback exportů | `frontend/shared/desktop-state/logic/api.ts` |
| Pravidla, rozhodnutí, tickety, workflow | `frontend/shared/desktop-state/logic/types.ts`, `frontend/editor/llm-control/project-memory/components/ProjectMemoryPanel.tsx`, `frontend/editor/workflow/components/NodeWorkflowPanel.tsx` |
| Live Run telemetrie sessions | `frontend/live-run/node-sessions/components/LiveWorkspacePanel.tsx` |
| HTTP hranice a hlavní routy | `backend/app/factory.py` |
| Validace grafu/sourceRef | `backend/canvas/graph.py` |
| Whole-state revize a packet routy | `backend/api/editor/desktop_v3_routes.py`, `backend/editor/agent_memory/desktop_v3_state.py` |
| Vazby sessions na uzel, Hermes zdroj | `backend/live_run/node_sessions.py` |
| Telemetrie agentů | `backend/api/live_run/agent_routes.py` |
| Zdrojové stromy a dokumenty workspace | `backend/project/workspace/workspace_sources.py` |

## Co bylo skutečně provedeno při sestavení

- Přečteny uvedené relevantní zdrojové kontrakty a UI handlers.
- GET health/bootstrap/build-identity na aktuálním localhostu.
- Pomocný skript spuštěn proti živému localhostu pro stav, projekty a view.
- Žádné spuštění modelu, UI klikání, zápis aplikačních dat nebo testovací sada.
- Nebyla spuštěna nová placená relace Claude pro zkoušku automatického aktivování.
  Instalace má standardní projektový formát; matching závisí na verzi a klientovi.

## Formát Claude Code skillu

Referenční dokumentace: https://code.claude.com/docs/en/skills
Přímé načtení této stránky při přípravě vrátilo HTTP 403. Nepředstíráme její
úspěšné stažení. Formát odpovídá podkladům uživatele a projektovým skills
Claude Code: `name`, `description`, volitelná metadata a odkazy na pomocné soubory.

Bezpečnostní upřesnění k podkladům: obecný Bash umí zapisovat, takže
`allowed-tools: Read, Grep, Glob, Bash` sám neprokazuje read-only provoz.
Tento skill nepředpovoluje Bash. Skript přitom obsahuje pouze GET a běží pod
běžným schválením nástrojů. Skutečné zákazy je nutné vynutit oprávněními klienta.
