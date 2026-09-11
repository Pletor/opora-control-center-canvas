# Export/readback scope hardening — handoff (lane: fix/v3-export-scope-hardening)

Base: 2ab5fa97dc926af2239dc4be08ccaa7360657b4b. Status: DONE — RED reproduced, GREEN verified. Backend untouched.

## Problem (reproduced with adversarial fixture)
- `exportHandoff()` (`src/desktop-v3/api.ts`) modelled only `{id,digest,task,context}`, although
  `backend/task_handoffs.py export()` returns `id,digest,scope,task,allowedFiles,readableNodeIds,context,provider,model,budgetSeconds`.
- `LiveWorkspacePanel.readContext` and the `AgentPacketPanel` export button checked only id/digest: an export with a
  foreign/missing/malformed `scope` (or missing `context`) was displayed and downloaded.
- `AgentPacketPanel` snapshot readback checked only the digest: wrong id / foreign project/workspace / missing
  `packet.scope` was reported as "Snímek načten neměnný".

## Fix (only allowed paths)
- `api.ts`: new `HandoffExport` (exact backend shape), `HandoffExportExpectation`, `assertHandoffExport` (fail-closed:
  object body, string `task`, present `context`, exact id+digest, well-formed `scope` with string project/workspace and
  string|null node, exact project/workspace/node match). `exportHandoff(expected)` always validates — no caller can
  obtain an unvalidated export. New `SnapshotReadbackExpectation`, `assertSnapshotReadback`; `fetchSnapshot(expected)`
  validates id, digest and `packet.scope` project/workspace/nodeId.
- Valid payload is returned as the same object → display/download stays byte-identical to server JSON (tested).
- `LiveWorkspacePanel`: expected = selected run id/digest, panel project/workspace, `handoff.scope.node`; clears the
  previous context before a new read so an error is never shown next to stale data. Generation race guard unchanged.
- `AgentPacketPanel`: export expected = run id/digest, panel project/workspace, `run.scope.node`; ticket race guard
  unchanged (stale responses — valid or invalid — are dropped silently). Stop/start guards untouched; no new requests.

## Tests (isolated port 8793, `playwright.export-scope.config.ts`, reuses e2e-v3-panels harness+fixture via Vite `--port`)
- `npx playwright test -c playwright.export-scope.config.ts` → base source: 18 failed / 11 passed (RED);
  fixed source: 29 passed (GREEN).
- `EXPORT_SCOPE_REGRESSION=1 npx playwright test -c playwright.export-scope.config.ts` (export-scope + agent-packet +
  live-workspace specs) → 38 passed.
- `npx tsc --noEmit` → exit 0.

## Compatibility requirements for coordinator
1. `e2e-v3-panels/fixture-plugin.ts` (not owned by this lane) GET `/api/task-handoffs/{id}/export` returns
   `{id,digest,task,context}` without `scope`. Against that unmodified fixture the AgentPacketPanel export now fails
   closed ("Export nemá platný rozsah projektu, prostředí a uzlu."). No existing spec asserts a successful export via
   the fixture, so nothing regresses, but the fixture should return the real backend shape (add
   `scope: run.scope, allowedFiles, readableNodeIds, provider, model, budgetSeconds`).
2. `src/TaskHandoffPanel.tsx` (legacy, non-v3, outside write scope) has its own export via `api()` with id/digest-only
   checks; `e2e-document-task` mocks omit `scope`. Not hardened here.
3. API signature changes: `exportHandoff(id)` → `exportHandoff(expected)`, `fetchSnapshot(id,project,workspace)` →
   `fetchSnapshot(expected)`. Only consumers are the two panels (updated). Other lanes calling the old signatures
   would fail `tsc`, not silently bypass validation.
