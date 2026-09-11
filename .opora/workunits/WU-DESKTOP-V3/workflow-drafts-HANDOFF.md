# WU-DESKTOP-V3 — v3 failed-save draft preservation

Branch: `fix/v3-workflow-draft-preservation`
Worktree: `C:/Users/Admin/opora-v3-workflow-drafts`
Base of lane: `2ab5fa97dc926af2239dc4be08ccaa7360657b4b`; first candidate `2de3c4e` (failed independent
review); this correction is committed on top of `2de3c4e`.
External evidence: `C:/Users/Admin/AppData/Local/hermes/handoffs/canvas-orchestration/desktop-v3/workflow-drafts-post-reset/`

## Original defect (fixed in 2de3c4e, kept)

`addCriterion`/`addStep` (NodeWorkflowPanel) and `addSetting`/`addRule`/`addDecision`
(ProjectMemoryPanel) cleared the draft unconditionally, even when `mutate()` returned `false`
(409/500/network). `run()` now returns the `mutate()` boolean and drafts are cleared only on success.

## Review blockers on 2de3c4e and their correction

1. **HIGH, silent data loss.** 2de3c4e replaced the single busy flag with per-node busy scopes. But
   all nodes share one `useDesktopState` snapshot with one revision and no mutation fencing. So B
   (n2) could be POSTed while A (n1) was still in flight. B succeeded as R1 (carrying A's
   optimistic state). A then failed with 409/500 and rolled the screen back to S0 while the
   revision stayed R1. The next save then passed CAS and erased A and B on the server.
   **Correction:** one synchronous, panel-wide save lock (`saveLockRef`) in both panels. `run()`
   returns `false` immediately while a save is pending: nothing is sent, nothing is queued, and
   failed optimistic state is never piggybacked on a later save. The lock is released only in a
   `useLayoutEffect` keyed on a settle counter. That effect runs after the render that commits the
   settled result (success or rollback), so the next handler's `mutate` closure has fresh
   state/revision. Cleanup runs in `finally`. The per-node `busyScopes` set and the per-handler
   `if (busy) return` render-closure guards were removed; the ref lock replaces them.
2. **LOW, A→B→A cleared a newer draft.** 2de3c4e used a scope equality check, but drafts are shared
   across nodes. **Correction:** per-draft version refs (`criterionDraftVersion`, `stepDraftVersion`
   for the step text+assignee tuple, `settingDraftVersion` for the key+value tuple,
   `ruleDraftVersion`, `decisionDraftVersion`). Every `onChange` increments the version. A
   successful save clears the draft only if the version is the same one captured at submit. The
   scope check (`scopeRef`) was removed.

## Semantics / UX

- NodeWorkflowPanel: while any save is pending, every mutating control (add buttons, checkboxes,
  remove, advance, earlier-phase tabs) is disabled on **every** node. This is a panel-wide lock,
  intentionally not per-node. Draft text inputs (criterion, step, assignee) stay editable during a
  save (only `readOnly` disables them), so typing for another node is still possible, as the
  per-node typing test requires. Enter while saving does nothing, sends no POST and keeps the draft.
- ProjectMemoryPanel: controls keep their previous `disabled={readOnly || busy}` shape (no visual
  change). The sync lock also covers `editSetting`/`removeSetting`/`removeRule`/`togglePin`, which
  previously had no synchronous guard.
- Read-only `main` still disables all inputs and controls; `mutate` still refuses to write.
- Markup/layout unchanged apart from the `disabled` attribute on NodeWorkflowPanel draft inputs
  during a save.

## Tests (`e2e-v3-panels/workflow-draft-preservation.spec.ts`, 9 cases)

New:
1. `held save for n1 blocks a concurrent save for n2; both persist across reload and a further mutation`:
   holds A's POST, switches to n2 via the hash, types B, presses Enter, and asserts the in-page POST
   counter is still 1 (the counter wraps `fetch` synchronously, so this is deterministic without
   sleeps). Releases A (200), waits for the add button to be enabled, saves B (200), reloads, and
   checks A on n1 and B on n2. It then checks the A checkbox (200), reloads, and asserts A (checked)
   and B are both still present.
2. `failed held save for n1 is not persisted piggyback via the next successful save for n2`: same
   flow, but A gets a 500. After B is saved and the page reloads, n1 has no criterion and n2 has B.
3. `A→B→A: late success for n1 keeps a draft newly typed on n2 and still shown on n1`.

Changed: the scope-switch test's `waitForTimeout(300)` was replaced with `waitForResponse` on the
released POST plus a wait until the add button is enabled (it unlocks only in the render that
settled A).
Unchanged: 409/500 failure recovery (criterion, step+assignee, setting key+value) and both
double-Enter tests.

## RED / GREEN (raw logs with exit codes in the external dir)

- `partial-NodeWorkflowPanel.patch`: the uncommitted partial patch left by the interrupted
  pre-reset session (async queue + `setTimeout(0)`). It was preserved and then discarded (the file
  was restored from HEAD by an explicit write). It is not the basis of this fix.
- `01-red-race-on-HEAD.log` (exit=1): the new race tests failed on unmodified `2de3c4e` source at the
  POST-count assertion, `Expected: 1, Received: 2`. The n2 save was really sent while n1's save was
  held. The other 6 passed.
- `02-green-race-lock.log` (exit=0): 8 passed after the panel-wide lock. `02-tsc-after-lock.log` exit=0.
- `03-red-aba-on-lock.log` (exit=1): the new A→B→A test failed on the lock-only code with
  `Expected: "Novější koncept", Received: ""`, because the scope check cleared the newer draft.
  The other 8 passed.
- `04-green-final-playwright.log` (exit=0): 9 passed after the draft versions.
  `04-tsc-final.log` exit=0; `04-diff-check.log` exit=0.

Commands: `node node_modules/@playwright/test/cli.js test -c playwright.workflow-drafts.config.ts`
(private port 8794), `node node_modules/typescript/bin/tsc --noEmit`, `git diff --check`.

Correction of the earlier note: the previous handoff said `tsc` had "pre-existing e2e/*.spec.ts
errors". That was inaccurate. In this tree, `tsc --noEmit` exits 0 with no errors.

## Limitations

- A mutation attempted while a save is pending is dropped, not queued. The user retries manually
  and the draft is kept. For ProjectMemoryPanel's per-keystroke `editSetting`, a keystroke that
  arrives between submit and the disabled render is dropped instead of racing.
- The lock is per mounted panel instance. Two separate panels on the same project/workspace each
  hold their own `useDesktopState`; conflicts between them still surface as a visible CAS 409
  (no silent overwrite), not as serialization. Fixing that needs a shared store contract (not
  owned here).
- Clicking "Znovu načíst" mid-flight makes `mutate` return `false` even if the server later
  commits; the draft stays and a retry gets a 409 or a duplicate. This is pre-existing, reported by
  the reviewer, and not changed.
- Drafts are still shared across nodes. A draft typed on n2 remains visible after switching to n1.
  If it is submitted unchanged and succeeds, it is cleared even after a node switch, because
  exactly that text was persisted.
- The shared `playwright.desktop-v3.config.ts` suite (port 8782) was not run in this pass (private
  port 8794 only). A grep of `node-workflow.spec.ts`/`project-memory.spec.ts` shows disabled-state
  assertions only for Postoupit/phase tabs and read-only `main`; both are preserved.
- Independent re-review and integration are coordinator responsibilities; this is not
  self-approval.
