# Sonnet lane — Desktop v3 panels — HANDOFF

Scope: `src/desktop-v3/*`, `e2e-v3-panels/*`, `playwright.desktop-v3.config.ts`, `vite.desktop-v3.config.ts`.
No App/main/backend/global-theme files touched. No push/deploy/server restart performed.

## Owned/changed paths (this session)
- `src/desktop-v3/state-store.ts` — genuine bug fix (see below).
- `src/desktop-v3/AgentPacketPanel.tsx` — review gaps 1, 2, 3, 8.
- `src/desktop-v3/LiveWorkspacePanel.tsx` — review gaps 4, 5, 6.
- `src/desktop-v3/panels.css` — responsive manifest card list (gap 8).
- `e2e-v3-panels/harness.tsx` — hash-driven scope props so tests can exercise a scope change on
  the *same mounted component* (A→B→A) instead of only via full navigation/remount.
- `e2e-v3-panels/fixture-plugin.ts` — preview endpoint no longer requires a non-empty `sessionId`
  (empty string is a valid scope value per contract, not an error).
- `e2e-v3-panels/agent-packet.spec.ts` — new.
- `e2e-v3-panels/live-workspace.spec.ts` — new.

## node-workflow RED → GREEN (root cause + fix)
Root cause: `useDesktopState().mutate()` only called `setState()` **after** the network
round-trip resolved. A checkbox's `onChange` set `busy=true` synchronously (disabling the
control) while `checked` stayed at its old value until the `await saveState(...)` promise
settled. Playwright's `.check()` does a single post-click verification (no retry loop), so it
observed a checkbox that was now `disabled` and still unchecked, and failed immediately with
"Clicking the checkbox did not change its state".

Fix (`state-store.ts`): `mutate()` now applies the computed next state optimistically
(`setState(next)`) *before* awaiting the save, then reconciles with the exact server-returned
state on success, or rolls back to the previous confirmed state on failure/staleness. This is
not a UI-only patch — the persisted value is always the server's response, never the optimistic
guess; the "conflicting revision" CAS-rollback test (`project-memory.spec.ts`) still passes
unchanged, proving rollback-on-409 still shows the pre-mutation state and no phantom write.

RED (before): `.opora/workunits/WU-DESKTOP-V3/evidence-sonnet/red-node-workflow-initial.log` —
4 failed / 2 passed.
GREEN (after): `.opora/workunits/WU-DESKTOP-V3/evidence-sonnet/green-node-workflow-optimistic.log` —
6 passed. I did **not** touch the test file or weaken any `.check()` assertion.

## Review gaps addressed (SONNET-PRELIMINARY-REVIEW.md)
1. **sessionId** — `AgentPacketPanel` no longer generates a random `useRef(newId())` session id.
   It now accepts an optional `sessionId` prop (default `""`), sent verbatim as the packet
   scope's `sessionId`. Export filenames use a separate `exportNonce` (still random, but never
   sent to the API as a session). Fixture's preview endpoint updated to accept `""` as valid.
   Covered by `agent-packet.spec.ts` (2 tests: default empty, explicit value forwarded).
2. **Same-mount scope invalidation (A→B→A)** — `scopeSignature` is now watched by an effect that
   bumps `generation.current` and resets preview/snapshot/task/run/approved whenever the prop
   scope changes *without* an unmount. Any in-flight request tied to the old scope is dropped by
   the existing ticket check. Covered by `agent-packet.spec.ts` (delays node-a's response,
   switches to node-b and back to node-a before it resolves, asserts the stale response never
   populates the fresh node-a view).
3. **Stale snapshot/run cannot cross scopes; active run survives a new preview** — same effect as
   above clears `snapshot`/`run`/`approved` on real scope changes (so prepare/start/export can
   never fire against a snapshot from a different node), but `buildPreview()` no longer
   unconditionally clears `run` — it only clears it if the run is no longer active. Covered by
   `agent-packet.spec.ts` ("a new preview within the same scope does not remove an active run's
   stop control").
4. **LiveWorkspacePanel partial failure** — `Promise.all([...])` replaced with two independent
   fetches (`fetchPlanningRuns`, `fetchHandoffRuns`), each with its own loading/error state and
   retry button, both still gated by the same scope ticket. A failing planning-runs call no
   longer hides successfully loaded handoff runs (or vice versa). Covered by
   `live-workspace.spec.ts`.
5. **Genuine ticket creation** — added a real create form (title, priority select, optional
   session id) bound to the current `nodeId`, persisted via the existing CAS `mutate()` (same
   save+reload path as everything else in state-store), `createdBy: "human"` explicit — no
   fabricated agent identity. Covered by `live-workspace.spec.ts` (creates, verifies chip values,
   reloads the page, verifies persistence and a status change survives reload too).
6. **Context/axis section** — new "Kontext a osa" section merges real timestamped events: pinned
   decisions (`state.decisions`), handoff run events, and planning run updates, sorted
   descending by timestamp. Context-window size and compaction progress are not available from
   any endpoint this contract defines, so the panel renders an explicit
   "Kontextové okno: nedostupné · Průběh kompaktace: nedostupné" line instead of inventing
   numbers. The existing external agents catalog (AgentsWorkspace) is untouched/out of this
   lane's owned files. Covered by `live-workspace.spec.ts`.
8. **Manifest overflow at 320/390px** — replaced the fixed 5-column `<table>` with a wrapping
   flex "card" list (`v3-manifest-list`/`v3-manifest-item`); owner ids use `word-break: break-all`
   so long UUIDs wrap instead of forcing horizontal scroll, and prefer an optional
   `label`/`name` field on the manifest entry (if the backend ever adds one) over the raw
   `ownerId`, with the id kept as a `title` tooltip. Exact JSON remains available unchanged via
   the existing `<details>` block. Not covered by an automated viewport-width test this session
   (manual/visual verification only) — see Incomplete below.
7. **CLI logs** — every command below was run bare, no pipe into grep/tail/`||true`. Real exit
   codes recorded.

## Not addressed / incomplete (explicitly out of scope this session)
- Item 8 has no automated Playwright viewport assertion (e.g. `page.setViewportSize({width:320})`
  + no-horizontal-overflow check). The CSS change is real and testable manually; adding the
  assertion was deferred to stay within budget after the higher-priority correctness gaps (1–6)
  and the RED node-workflow tests.
- `AgentPacketPanel`/`LiveWorkspacePanel` still have no coverage for: stop→confirm→cancelled flow,
  export-handoff round trip, and the packet `<pre>` JSON view at narrow widths.
- This is all against the **fixture** mock server in `e2e-v3-panels/fixture-plugin.ts` (explicitly
  labeled as a mock, not the production Fable backend). It does not constitute production
  acceptance; the parent/coordinator still needs real API integration + browser QA against the
  actual `/api/desktop-v3/*` backend per CONTRACT.md.
- No changes made to `ProjectMemoryPanel.tsx`, `NodeWorkflowPanel.tsx`, or `types.ts`/`api.ts`
  beyond what's listed above — decisions still always save with `nodeId: ""` in
  `ProjectMemoryPanel.addDecision()` (pre-existing behavior, not touched, not in the review gap
  list, so left alone; the new "Kontext a osa" section still surfaces those decisions when no
  `nodeId` filter is active).

## Exact verification commands run (bare, real exit codes)
```
npx tsc --noEmit
  → exit 0   (.opora/workunits/WU-DESKTOP-V3/evidence-sonnet/green-tsc-final.log)

npx vite build --config vite.desktop-v3.config.ts
  → exit 0   (.opora/workunits/WU-DESKTOP-V3/evidence-sonnet/green-build-final.log)

npx playwright test --config playwright.desktop-v3.config.ts
  → exit 0, 20 passed, 0 failed
    (.opora/workunits/WU-DESKTOP-V3/evidence-sonnet/green-full-suite-final.log)
```
Breakdown: 6 node-workflow + 6 project-memory + 1 smoke (all pre-existing, all still pass) +
4 new agent-packet + 3 new live-workspace = 20.

RED evidence for the task's stated failing suite:
`.opora/workunits/WU-DESKTOP-V3/evidence-sonnet/red-node-workflow-initial.log` (4 failed / 2 passed,
before the `state-store.ts` fix).

## Verified vs still incomplete (summary)
**Verified (against the in-repo fixture mock, TDD RED→GREEN, real command exits):**
- Optimistic-then-reconciled `mutate()` fixes the 4 failing node-workflow checkbox tests without
  weakening any assertion; CAS-409 rollback still works correctly.
- `sessionId` is a real/explicit scope value, never a random local id; export nonce is separate.
- AgentPacketPanel correctly invalidates stale async responses across an A→B→A scope change on
  the same mounted instance, and no longer clears an active run when a new preview is built in
  the same scope.
- LiveWorkspacePanel isolates planning-run vs handoff-run fetch failures from each other.
- LiveWorkspacePanel can genuinely create a ticket (title/priority/node/session, human authorship,
  CAS-persisted, survives reload).
- New "Kontext a osa" section shows only real timestamped data, with explicit "nedostupné" for
  telemetry this API does not provide.
- Manifest is now a wrapping card list (no fixed-width UUID columns); build and typecheck are
  clean.

**Still incomplete / not claimed:**
- No automated 320/390px overflow regression test.
- No production/live-backend verification — all green runs are against the local fixture mock.
- No claim that the app or this feature set is "done"; parent/coordinator integration and real
  API QA is still required per CONTRACT.md.
