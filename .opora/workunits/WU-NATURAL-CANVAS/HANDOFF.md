# WU-NATURAL-CANVAS — HANDOFF (Opus writer, 2026-09-10)

Worktree: `P:/0. OSVC/8. Code/07. Aplikace/02.Opora-control-center/Opora-control-center-canvas/.worktrees/natural-canvas`
Větev: `feat/natural-canvas` · base `dbc19ff` · HEAD **`9647762`** (`fix(canvas): sjednotit detail uzlu do jednoho panelu`)
Předchozí commit této WU: `eda3cd8`. Diff base→HEAD: 19 souborů, +1761 / −23.

## Co tento běh skutečně udělal

1. **Zděděná necommitnutá práce předchůdce byla zachráněna, ne zahozena.** Před jakýmkoli zásahem uložena jako
   `.opora/workunits/WU-NATURAL-CANVAS/inherited-uncommitted.patch` (93 řádků, `src/App.tsx` + `src/NodePanel.tsx`).
   Žádný `git restore/reset/checkout` celého `src/`, žádný stash.
2. Zděděná změna byla přečtena a ověřena jako **chování zachovávající refaktor**: `NodeLinksPanel` a akce
   „Připravit úkol pro agenta“ se přesunuly z druhého `aside.detail-extras` v `App.tsx` dovnitř `NodePanel.tsx`.
   `readOnly={!!view?.readOnly}` i remount podle `view.digest` (přes `key` na `NodePanel`) zůstávají shodné.
   Zacommitnuto jako `9647762`, jen dvě vlastněné cesty (`git add src/App.tsx src/NodePanel.tsx`, nikoli `-A`).

## Stav testu „map shows actual hierarchy“ — NENÍ to nová regrese

`e2e/workspace-modes.spec.ts:43` v tomto pracovním stromu **prochází** (viz `e2e-target-1.log`, `e2e-full-1.log`).
RED se v tomto běhu **nepodařilo reprodukovat** a nebyla proto zaváděna žádná „oprava“.
Nejpravděpodobnější příčina domnělého RED u předchůdce (nedoloženo, hypotéza): `npm run build` v tomto worktree
končí exit 1 na kroku `scripts/copy-drawing-assets.mjs` (viz níže), takže `dist/` mohlo zůstat zastaralé,
a předchůdce navíc pipeoval výstup přes `tail/grep`, což maskuje exit code.
**Oddělená baseline reprodukce na `eda3cd8` v tomto běhu proběhnout nestihla** (wall deadline) — je to jediná
zbývající otevřená diagnostická položka, viz „Zbývající příkaz“.

## Build: reálné omezení prostředí (NEopraveno, cizí vlastnictví)

`npm run build` = `tsc --noEmit && vite build && node scripts/copy-drawing-assets.mjs`.
- `npx tsc --noEmit` → **exit 0**
- `npx vite build` → **exit 0** (`dist/` se vytvoří)
- `node scripts/copy-drawing-assets.mjs` → **exit 1**: `ENOENT ... .worktrees/natural-canvas/node_modules/@excalidraw/excalidraw/dist/prod/fonts`

Příčina: skript řeší cestu jako `resolve("node_modules/...")` vůči cwd, ale worktree **nemá vlastní `node_modules`** —
balíčky jsou hoistované v `Opora-control-center-canvas/node_modules` (tam `@excalidraw/excalidraw/dist/prod/fonts` existuje).
`scripts/copy-drawing-assets.mjs` **nevlastním** (patří drawing WU), proto jsem ho nezměnil.
Návrh pro rodiče: v tom skriptu použít `createRequire(import.meta.url).resolve("@excalidraw/excalidraw/package.json")`
místo cwd-relativní cesty. Do té doby `npm run build` v jakémkoli worktree bez lokálních `node_modules` končí exit 1
i při zdravém zdroji. E2E to neblokuje (`drawing.spec.ts` prošel).

## Acceptance z původního `natural-opus.md` — implemented / partial / missing

Ověřeno běžícím `e2e/natural-canvas.spec.ts` (prochází) a čtením zdroje.

| Acceptance | Stav | Důkaz |
|---|---|---|
| Dvojklik na prázdné plátno vytvoří uzel a hned in-place jméno | implemented | spec §1 |
| In-place přejmenování karty dvojklikem, bez dlouhého formuláře | implemented | spec §1 |
| Enter = sourozenec, Tab/Shift+Tab indent/outdent, kořen se nevynoří pod 0 | implemented | spec §2, `src/BlockOutline.tsx` |
| Slash paleta s klávesovými nápovědami + Escape | implemented | spec §3, `src/block-commands.ts` |
| `[[odkaz]]` vybírá existující uzel, stejná identita uzlu | implemented | spec §4, `GET /api/node-links/targets` |
| Debounced ukládání s pravdivým saving/saved/error + reload | implemented | spec §5 (`text-status`) |
| CAS konflikt zachová draft a řekne pravdu | implemented | spec §9 |
| Main read-only | implemented (starší cesta) | `readOnly` prop → `NodeLinksPanel`; pokryto `node-spec.spec.ts:56`, `drawing.spec.ts:168` |
| Skutečné počty souvislostí + klik naviguje na týž uzel | implemented | spec §6 (`link-out-count`, `link-out`) |
| Zpětné odkazy a hrany plátna ze stejné autority | implemented, **e2e nepokryto** | `src/NodeLinksPanel.tsx:77-79` (`link-in`, `link-edge`), `backend/node_links.py`, `tests/test_block_links.py` |
| Datovaný deník u téhož uzlu, ne druhý graf, escapování/XSS | implemented | spec §8, `backend/node_journal.py`, `tests/test_node_journal.py` |
| Kontextová akce vydá typovaný scope, žádný placený běh | implemented | spec §7 (`agent-task-notice`, kontrola `/api/*/start` requestů = 0) |
| „Navigace chrání rozepsané editace“ | **partial** | CAS/draft ano; explicitní guard při přepnutí uzlu pokryt jen pro spec editor (`node-spec.spec.ts:29`), pro blokový outline **není e2e** |
| IME / focus edge cases | **missing** | v `natural-canvas.spec.ts` není IME/composition test |
| Typový chooser vazby při drag handle→uzel (bod 3 UX mapy) | **missing** | mimo commitnutý rozsah |
| Mobilní chování nového outline/deníku | **missing** | žádný mobile test pro `node-blocks`/`journal-blocks` |

Nic z testů nebylo oslabeno ani smazáno; assertions beze změny.

## Kontrakt pro rodiče (integrace panelu Agenti)

- HTTP (moje routy v `backend/app.py`, implementace `backend/node_links.py`, `backend/node_journal.py`):
  `GET /api/node-links`, `GET /api/node-links/targets`, `GET /api/node-journal`, `POST /api/node-journal`,
  plus stávající `GET/POST /api/node-text`.
- `GET /api/node-links` → `{ outgoing, backlinks, edges: NodeLink[], counts: { outgoing, backlinks, edges, unresolved } }`.
- React props přidané na `NodePanel` (`src/NodePanel.tsx`):
  - `onOpenNode: (id: string) => void` — souvislost vede na tentýž uzel v plátně.
  - `onAgentTask: () => void` — vydá scope, **nespouští běh**.
- Payload pro panel agenta: `AgentTaskRequest` v `src/context-actions.tsx` (`emitAgentTask`), testid `agent-task-action`,
  `agent-task-notice`, `agent-task-node`, `agent-task-layer`. Rodič si na tento seam připojí skutečný panel.
- `src/types.ts` ani `backend/service.py`/`gitio.py` **nezměněny**; žádný paralelní graf, žádné `agent_*` moduly.

## Zbývající příkaz (neproběhl, neslibuji výsledek)

Baseline reprodukce domnělého RED na commitu `eda3cd8` v oddělené worktree (ne v této), poté:
`npx playwright test e2e/workspace-modes.spec.ts --reporter=list` (port 8741). Vyžaduje vlastní `dist/` a `.venv`.

## Stav worktree / co jsem nechal být

- **Necommitnuté zůstávají modifikované `evidence/*.png`** (přepsané běhy Playwrightu — částečně předchůdcem,
  částečně mým full-suite během) a netrackované `evidence/fractal-text.png`, `project-home-preview.png`,
  `wireframe-editing-preview.png`, `wireframe-editor.png`. **Nerevertoval jsem je naslepo** a nezacommitoval —
  nejsou to moje cesty a jde jen o výstup běhu testů. Rodič ať rozhodne.
- Žádný push/merge/rebase, žádná změna configu/credentials, žádný deploy, produkce 8740 a `.worktrees/project-wireframe`
  nedotčeny. Testovací procesy (uvicorn 8741 pod Playwright webServer) skončily s během testů.
