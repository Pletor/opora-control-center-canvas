# Live Run — Desktop v3 preview checkpoint

## Delivered scope
- Replaced the new Live Run main view with the three-column structure of the downloaded `06 OPORA Desktop v3.dc.html` (reference lines 443–488): sessions, detail with seven tabs, side thread/control pane.
- The primary view consumes real project/workspace-scoped planning and documentation-handoff APIs. A completed proposal is explicitly NOT an implemented/tested application change.
- Full stored output is directly visible and downloadable. Unknown costs/context telemetry remain unavailable, not zero. Unsupported /btw, correct, resume and compact transports are disabled with explanations.
- Existing external AgentsWorkspace remains the separate advanced "Dohled běhů" view; it has NOT been claimed as a rebuilt or project-scoped external runtime transport.
- Plan stop uses POST `/api/llm/stop` with exact project/runId/confirmed, then a fresh list readback. Handoff stop uses its own endpoint and exact run/scope readback. No model starts occur on opening/refreshing.
- Source reads are independent, abort after 8 seconds, do not overlap per source, and pause while hidden. Stop/read fencing prevents a stale poll restoring a terminal run to running. Refresh retains selected session/tab and does not strand a pending stop confirmation.
- Tickets are CAS-persisted with explicit human authorship, selected session/node scope, read-only main and displayed errors.

## Verification actually executed
- `npx tsc --noEmit`: PASS.
- `npx playwright test --config playwright.desktop-v3.config.ts --reporter=list`: **26 passed**. Includes RED→GREEN layout/output, real stop endpoint, stalled source, refresh retention and stop-refresh regression. Stale poll regression passes.
- `uv run pytest tests/test_llm_runs.py tests/test_task_handoffs.py -q`: **14 passed, 1 skipped**, two existing dependency deprecation warnings.
- `node node_modules/vite/bin/vite.js build --outDir .data/v3-live-dist --emptyOutDir`: PASS; existing large bundle warnings remain.
- Static scan over changed/new UI: no raw HTML/eval/external URL findings; `git diff --check`: PASS.
- Independent read-only review first identified stale poll overwrite and incorrect handoff list limit; fixed. Follow-up `deleg_b8b4c61e` reports passed, empty security/logic concerns; its own six regression tests passed. Review transcript: `C:/Users/Admin/AppData/Local/hermes/cache/delegation/live/deleg_b8b4c61e/task-0.log`.

## Running preview and evidence
- URL: http://127.0.0.1:8780/?screen=canvas&project=4b38182c5b04482bb00e0f3d3ae55656&workspace=draft&environment=live
- Uses `.data/v3-preview-copy`, NOT the live 8768 database.
- Both actual proposal outputs compared against GET API, byte/text content preserved: two runs; seven tabs; no page errors and zero POST requests while viewing, switching outputs/themes, and checking widths 1280/1440/1920.
- Static publish verified served index matches built index, SHA256 `2c331b3baea9e12f2a5c8eb95c495be6926edd8978a43b980cfa6487d77911f7`.
- Evidence root: `C:/Users/Admin/AppData/Local/hermes/handoffs/canvas-orchestration/desktop-v3/`.
- `verify-live-redesign.cjs`, `live-preview-evidence.json`, `live-redesign-light.png`, `live-redesign-dark.png`, `publish_live_preview.py`.
- Only the test frontend on 8780 was updated. Original 8768/8740 processes and data were not changed.

## Not asserted complete
- Full Desktop v3 delivery and legacy regression suite are NOT declared green. Earlier legacy UI result was 90 pass / 2 fail / 1 skip. A separate session-packet acceptance test remains RED in uncommitted work, outside this Live Run checkpoint.
- No real paid model was started/stopped during this checkpoint; stop semantics exercised with controlled endpoint tests and existing backend tests.
- Historic planning API omits provider/model/context; handoff public API omits timestamps/worktree. UI reports these fields unavailable. No runtime facts inferred from current project settings.
- Optional reviewer hardening: additionally check export.scope alongside immutable id/digest before displaying a handoff snapshot.
- External catalog adapter currently includes non-run artifact folders; investigate separately before claiming an exhaustive true external-session list. New project session view does not consume that catalog.
