# WU-DESKTOP-V3 — v3 failed-save draft preservation (Sonnet)

Branch: `fix/v3-workflow-draft-preservation`
Worktree: `C:/Users/Admin/opora-v3-workflow-drafts`
Base: `2ab5fa97dc926af2239dc4be08ccaa7360657b4b`

## Defect reproduced

`NodeWorkflowPanel.addCriterion`/`addStep` and `ProjectMemoryPanel.addSetting`/`addRule`/`addDecision`
all called `run(fn).then(() => clearFields())` unconditionally. `run()` discarded the `boolean`
returned by `state-store.mutate()`, so a failed write (409 revision conflict, 500, network error)
still cleared the just-typed draft even though nothing was saved.

Additionally, `NodeWorkflowPanel` tracked a single global `busy` boolean shared by every node.
Since the harness (and, structurally, the app) can change the `nodeId` prop on an already-mounted
panel (no remount), a pending write for node A left node B's controls disabled/tied to the same
flag, and a late-arriving response for A had no way to know the panel had since moved on to B.

## Fix (owned files only)

- `src/desktop-v3/NodeWorkflowPanel.tsx`:
  - `run()` now returns the `mutate()` boolean.
  - Busy state is now a `Set<string>` of in-flight scope keys (`project::workspace::nodeId`)
    instead of one global flag. Controls for the *currently displayed* node are disabled only
    while a write for **that same scope** is pending; switching to a different node while a
    write is in flight leaves the new node's controls interactive immediately.
  - `addCriterion`/`addStep` capture `requestScope` at submit time and only clear their draft
    fields when the write succeeded **and** the panel is still showing that same scope
    (`scopeRef.current === requestScope`) when the response arrives. Failure or a scope switch
    in the meantime preserves the draft untouched.
  - Added `if (busy) return;` guards at the top of every mutating handler (add/toggle/remove/
    advance/goToEarlierPhase) to prevent duplicate submits from rapid Enter/click while a request
    for that scope is already pending.
- `src/desktop-v3/ProjectMemoryPanel.tsx`: same pattern — `run()` returns the boolean,
  `addSetting`/`addRule`/`addDecision` only clear their draft on a successful write in the same
  `project::workspace` scope, and gained `if (busy) return;` double-submit guards. (Project/
  workspace cannot change on an already-mounted `ProjectMemoryPanel` in the current harness/app —
  they come from fixed props — so a single global `busy` flag remains correct there; no per-scope
  `Set` was needed.)
- No changes to `state-store.ts`, `api.ts`, `types.ts`, or `AgentPacketPanel.tsx` (other lanes own
  those). Visual output/markup unchanged; only handler logic and the busy-tracking shape changed.

## New test assets (own paths)

- `e2e-v3-panels/workflow-draft-preservation.spec.ts` — 6 new cases:
  1. 409 conflict preserves typed criterion text; retry with the still-present draft then persists
     and clears it.
  2. 500 failure preserves step text **and** assignee together; nothing was added to the list.
  3. A pending criterion save for node `n1` does not clear a criterion draft freshly typed for
     node `n2` after switching (via the harness's hash-based scope override, i.e. same mounted
     component, no navigation) while `n1`'s response is still in flight; switching back confirms
     `n1`'s criterion was in fact saved (not silently dropped).
  4. Rapid double `Enter` on the criterion input sends exactly one POST and adds exactly one
     criterion.
  5. ProjectMemoryPanel: 409 conflict preserves the new setting's key **and** value; retry then
     persists and clears both.
  6. ProjectMemoryPanel: rapid double `Enter` on the decision input sends exactly one POST and
     adds exactly one decision.
  - Reused the existing `**/api/desktop-v3/state` route-interception pattern from
    `node-workflow.spec.ts`/`project-memory.spec.ts`; did not modify those files or
    `fixture-plugin.ts`/`harness.tsx`.
- `vite.workflow-drafts.config.ts` — new Vite config, reuses the shared `fixturePlugin()` and the
  shared `e2e-v3-panels` harness root unmodified, own port **8794** (`strictPort: true`).
- `playwright.workflow-drafts.config.ts` — new Playwright config, `testMatch` scoped to
  `workflow-draft-preservation.spec.ts` only, `baseURL` `http://127.0.0.1:8794`, spawns the vite
  config above. Does not touch `playwright.desktop-v3.config.ts` (port 8782, another lane's
  regression suite) or any of 8742/8769/8771/8782/8793/8780.

### Not attempted: a same-project-switch leak test for `ProjectMemoryPanel`

The harness (`e2e-v3-panels/harness.tsx`, not owned) reads `project`/`workspace` only from the
initial URL query string, with no hash override (unlike `nodeId`/`path`/etc.). So on this harness
a project/workspace change is always a full `page.goto` (fresh mount, fresh local state) — no code
path exists to reproduce a same-mount project-scope leak for this panel without editing the shared
harness, which is out of scope. The scope-guard code was still added to `ProjectMemoryPanel` for
symmetry/robustness; only the two harness-testable behaviors (failed-save draft preservation,
double-submit) are covered by an automated test here.

## Commands run (this worktree)

```
npm ci --ignore-scripts                                             # fresh tree, no node_modules
npx tsc --noEmit -p .                                                # clean except pre-existing
                                                                      # e2e/*.spec.ts errors (missing
                                                                      # @types/node / playwright types
                                                                      # in tsconfig scope — pre-existing,
                                                                      # unrelated to this change, not in
                                                                      # owned paths)
```

RED (source reverted to base commit `2ab5fa9` via `git checkout HEAD -- src/desktop-v3/NodeWorkflowPanel.tsx src/desktop-v3/ProjectMemoryPanel.tsx`, new test file kept):
```
npx playwright test --config playwright.workflow-drafts.config.ts
# 4 failed / 2 passed — exactly the 4 draft-loss cases (409/500/scope-switch/setting-conflict)
# failed as expected; the two double-submit guard cases already passed on the unfixed code.
```

GREEN (fix restored):
```
npx playwright test --config playwright.workflow-drafts.config.ts
# 6 passed (4.8s)

npx playwright test --config playwright.desktop-v3.config.ts node-workflow.spec.ts project-memory.spec.ts smoke.spec.ts
# 13 passed (6.4s) — no regressions in the pre-existing suite for these two panels
```

Final typecheck: `npx tsc --noEmit -p .` — clean for all `src/desktop-v3/*` and the new spec/config
files (remaining errors are pre-existing, in unrelated `e2e/*.spec.ts` files not touched by this
change, unaffected by `node_modules` install).

## Limitations / follow-ups for other lanes

- `AgentPacketPanel.tsx` was not inspected/touched (owned by another lane per the assignment).
- Did not run the full repository-wide Playwright suite (would collide with concurrently running
  lanes on shared ports); only ran the isolated new config plus the specific pre-existing
  `e2e-v3-panels` files relevant to the two owned panels, on their own existing port (8782, not
  reserved by this lane, already free between runs here).

## Result

Small, verified change on owned paths only. Exact SHA of the commit containing this fix + tests +
handoff is recorded in the commit that follows this file (see `git log -1`).
