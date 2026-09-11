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
| Přepínání prostředí, URL a vytváření uzlů | `src/App.tsx` |
| Projekt/workspace, menu | `src/TopBar.tsx` |
| Módy plátna | `src/ModeRail.tsx`, `src/workspace-settings.ts` |
| Inspektor uzlu | `src/NodePanel.tsx` |
| Text a zadání, revize | `src/NodeTextEditor.tsx`, `src/NodeSpecEditor.tsx` |
| Reference a zakázané cesty | `src/workspace-selection.ts` |
| Vstup práce s AI | `src/EditorWorkbench.tsx` |
| Snapshot / schválení běhu | `src/desktop-v3/AgentPacketPanel.tsx` |
| Klientské API a readback exportů | `src/desktop-v3/api.ts` |
| Pravidla, rozhodnutí, tickety, workflow | `src/desktop-v3/types.ts`, `src/desktop-v3/ProjectMemoryPanel.tsx`, `src/desktop-v3/NodeWorkflowPanel.tsx` |
| Skutečné Live Run a neaktivní transporty | `src/desktop-v3/LiveWorkspacePanel.tsx` |
| HTTP hranice a hlavní routy | `backend/app.py` |
| Validace grafu/sourceRef | `backend/graph.py` |
| Whole-state revize a packet routy | `backend/desktop_v3_routes.py`, `backend/desktop_v3_state.py` |
| Handoff routy a omezení | `backend/task_handoff_routes.py`, `backend/task_handoffs.py` |
| Zdrojové stromy a dokumenty workspace | `backend/workspace_sources.py` |

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
