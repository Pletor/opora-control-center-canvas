# Live keyboard — candidate handoff

Base: `7bc61e575af116377a1ca4a4acade02ec90b9c6d`. Inventory: V3-KEY-003.
Status: CANDIDATE, not accepted or published. Coordinator recovered after Sonnet max-turns30, no permission denials, not quota. Windows Job inactive, original root57132 and child62716 absent; worktree HEAD/status stable before takeover. No source code changed by coordinator.

## Behavior
Digits1–7 select Live Run detail tabs. Input/textarea/select/contenteditable and modifier/composition events are ignored. Listener is removed on unmount. No backend changes or API writes introduced.

## Evidence
E = C:/Users/Admin/AppData/Local/hermes/handoffs/canvas-orchestration/desktop-v3.
- E/live-keyboard/red.log: first behavior failed because tab5 aria-selected was false instead of true, not a test syntax/import error.
- E/live-keyboard/green-full.log: 7 passed; originating agent did not commit or write a handoff before max-turns.
- Coordinator executed in this worktree: `node node_modules/@playwright/test/cli.js test -c playwright.desktop-v3.config.ts` → 75 passed, 31.0s, exit0 (all current panel specs, includes7 new tests).
- Same chained invocation: `node node_modules/typescript/bin/tsc --noEmit` and `git diff --check` → exit0.

## Limits
Candidate needs independent Claude review, integration regression and published8780 browser readback. The textarea test enables a disabled DOM field only in the fixture to exercise the editable guard; production side-thread transport remains missing. Contenteditable and composition are guarded but not directly covered by tests. This is not proof that all Desktop v3 components are functional. Private8796 config retained for isolated repeat, shared8782 suite automatically includes the new spec.
