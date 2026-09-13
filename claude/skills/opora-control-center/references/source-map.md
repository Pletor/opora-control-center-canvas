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
| Přepínání prostředí, URL a vytváření uzlů | `frontend/app/App.tsx` |
| Projekt/workspace, menu | `frontend/layout/top-bar/TopBar.tsx` |
| Módy plátna | `frontend/layout/mode-rail/ModeRail.tsx`, `frontend/project-detail/workspace/workspace-settings.ts` |
| Inspektor uzlu | `frontend/node-detail/NodePanel.tsx` |
| Text a zadání, revize | `frontend/node-detail/content/NodeTextEditor.tsx`, `frontend/node-detail/assignment/NodeSpecEditor.tsx` |
| Reference a zakázané cesty | `frontend/project-detail/workspace/workspace-selection.ts` |
| Vstup práce s AI | `frontend/layout/shell/EditorWorkbench.tsx` |
| Snapshot / schválení běhu | `frontend/agents/desktop-v3/AgentPacketPanel.tsx` |
| Klientské API a readback exportů | `frontend/agents/desktop-v3/api.ts` |
| Pravidla, rozhodnutí, tickety, workflow | `frontend/agents/desktop-v3/types.ts`, `frontend/agents/desktop-v3/ProjectMemoryPanel.tsx`, `frontend/agents/desktop-v3/NodeWorkflowPanel.tsx` |
| Skutečné Live Run a neaktivní transporty | `frontend/agents/desktop-v3/LiveWorkspacePanel.tsx` |
| HTTP hranice a hlavní routy | `backend/app/factory.py` |
| Validace grafu/sourceRef | `backend/domain/graph/graph.py` |
| Whole-state revize a packet routy | `backend/api/desktop_v3_routes.py`, `backend/agents/packets/desktop_v3_state.py` |
| Handoff routy a omezení | `backend/api/task_handoff_routes.py`, `backend/agents/runs/task_handoffs.py` |
| Zdrojové stromy a dokumenty workspace | `backend/integrations/workspace_sources.py` |

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
