# Export fixture/backend parity — handoff (lane: fix/v3-export-fixture-parity)

Base: f24f8f0. Status: CANDIDATE — RED reproduced against the real (unmocked) fixture, GREEN logs completed. Claude exited error_max_turns35 before commit (not quota). Coordinator verified inactive Windows Job, absent PID48724, free port8793 and stable worktree, then preserved and committed this candidate. Independent review and integration gates remain pending.
No production `src/`/`backend/` changes; fixture-only fix, as required by
[export-scope-HANDOFF.md](export-scope-HANDOFF.md) compatibility item 1.

## Problem

`e2e-v3-panels/fixture-plugin.ts` `GET /api/task-handoffs/{id}/export` returned only
`{ id, digest, task, context: { fixture: true } }`. The real backend
(`backend/task_handoffs.py` `TaskHandoffService.export()`, lines 448–466) returns
`{ id, digest, scope, task, allowedFiles, readableNodeIds, context, provider, model, budgetSeconds }`.

The hardened client (`src/desktop-v3/api.ts` `assertHandoffExport`, added by the export-scope-hardening
lane) fails closed on any export missing a well-formed `scope`. Against the old fixture, clicking
"Exportovat přesné zadání" in `AgentPacketPanel.tsx` (line 427) always threw "Export nemá platný
rozsah projektu, prostředí a uzlu." — the download never fired, even though existing specs passed
(none of them exercised the real, unmocked fixture export; they only exercise
`assertHandoffExport` via `page.route` stand-ins in `export-scope.spec.ts`).

## Fix (only `e2e-v3-panels/fixture-plugin.ts` touched — see `fixture-plugin.diff`)

- `prepareMatch` handler (POST `.../snapshots/:id/prepare`): the stored `HandoffEntry` now also
  captures `allowedFiles: ["result.md"]`, `readableNodeIds: [nodeId]`, and an immutable `context`
  object built once from the snapshot's own already-immutable fields (`schema`, `scope`,
  `snapshotId`, `digest`, `sourceManifest`, `warnings`, `task`) — mirroring
  `TaskHandoffService._snapshot_context` (lines 272–297) without copying its exact internal shape
  (fixture stays obviously synthetic: `provider`/`model` remain the literal strings
  `"fixture"`/`"fixture-model"`).
- `exportMatch` handler (GET `.../export`): now returns
  `{ id, digest, scope, task, allowedFiles, readableNodeIds, context, provider, model, budgetSeconds }`
  read directly from the stored run entry — never recomputed from current/live state, so a later
  preview or state mutation in the same scope cannot change an already-prepared run's export.
- Did not touch `assertHandoffExport`/`exportHandoff` (client fail-closed validation unchanged,
  per instructions — "do NOT weaken client validation").

## Tests (new file `e2e-v3-panels/export-fixture-parity.spec.ts`, isolated port 8793,
new `playwright.export-fixture-parity.config.ts`, reuses `vite.desktop-v3.config.ts` + the
existing fixture/harness, same pattern as `playwright.export-scope.config.ts`)

Both tests exercise the full UI vertical (preview → snapshot → readback → prepare → export
download) against the **real, unmocked** fixture — no `page.route` fulfillment replaces `/export`
in either test.

1. `prepared run export matches the real backend shape and the saved snapshot, with zero /start
   requests` — builds a preview, creates a snapshot, verifies its readback ("Snímek načten
   neměnný"), prepares a run, then downloads the export via the UI button and asserts
   `id`/`digest`/`scope`/`task`/`allowedFiles`/`readableNodeIds`/`provider`/`model`/`budgetSeconds`
   match the prepared run and the saved snapshot (`context.snapshotId`, `context.digest`), that no
   `p.v3-error` was raised, and that zero requests to `/api/task-handoffs/*/start` were ever made
   (no-model proof, alongside `provider`/`model` being the obviously-synthetic
   `"fixture"`/`"fixture-model"`).
2. `export context stays the original prepared snapshot after a later preview mutates the same
   scope` — after preparing a run with note `"original note"`, calls
   `POST /api/desktop-v3/packet/preview` directly (bypassing React state) in the same scope with
   note `"mutated note"`, then fetches `/export` for the already-prepared run twice; asserts both
   calls are byte-identical and the context still contains `"original note"`, never
   `"mutated note"` — the fail-closed immutability guarantee.

### RED (base fixture, before fix) — `red-new-spec-only.log`
```
Running 2 tests using 1 worker
  x 1 ... zero /start requests: Test timeout of 30000ms exceeded (page.waitForEvent: "download" never fired — client rejected the malformed export)
  x 2 ... mutates the same scope: Expected substring "original note", received "{\"fixture\":true}"
2 failed
EXIT:1
```

### GREEN (fixed fixture) — `green-new-spec-only.log`
```
Running 2 tests using 1 worker
  ok 1 ... zero /start requests (563ms)
  ok 2 ... mutates the same scope (306ms)
2 passed (3.8s)
EXIT:0
```

### Full regression — `EXPORT_SCOPE_REGRESSION=1 npx playwright test -c
playwright.export-fixture-parity.config.ts` (export-fixture-parity + export-scope + agent-packet +
live-workspace specs, same private port 8793, `workers: 1`) — `green-full-regression.log`
```
40 passed (20.0s)
EXIT:0
```

### `npx tsc --noEmit` — `typescript-check.log`: `EXIT:0` (no output)
### `git diff --check` — `git-diff-check.log`: `EXIT:0` (no output)

All raw logs (RED, GREEN, full regression, tsc, diff --check) and the fixture diff are saved under
`C:/Users/Admin/AppData/Local/hermes/handoffs/canvas-orchestration/desktop-v3/export-fixture-parity/`.

## Limits / out of scope

- Did not touch `src/TaskHandoffPanel.tsx` (legacy non-v3 panel, outside write scope) — its own
  export path and `e2e-document-task` mocks are unaffected by this fixture change.
- Did not touch `backend/task_handoffs.py`, `src/desktop-v3/api.ts`, or `AgentPacketPanel.tsx` —
  read-only inspection to source the exact real shape; no assertions were weakened or added there.
- `readableNodeIds` in the fixture is a single-element array (`[nodeId]`); the real backend can
  include neighbor node ids from `packet["included"]` (`prepare()`, line 218–221) — the fixture's
  in-memory packet model doesn't have a neighbor concept, so this is a deliberate synthetic
  simplification, not a hidden gap (no test asserts more than the current node is present).
- Did not touch ports 8780/8740/8768/8742/8769/8771/8782/8794/8795 or `NodeWorkflowPanel`/
  `ProjectMemoryPanel`; new webServer only binds 8793 and exits with the test process
  (`reuseExistingServer: false`, standard Playwright teardown, same as `export-scope.config.ts`).
- No merge/push/reset/clean performed; worktree left with only the intended file changes (see
  `git status` in logs) for the coordinator's independent review before merge.
