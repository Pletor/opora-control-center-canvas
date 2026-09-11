# Project tree actions — vertical re-implementation handoff (candidate, NOT accepted)

Branch `feat/v3-project-tree-actions`. Rejected candidate 8393b04 stays in history (no reset/clean/rebase).
Before any source was read, `src/SourceExplorer.tsx` and `src/ProjectWorkspace.tsx` were restored from `git show 959f879:PATH`.
The rejected `src/project-tree-actions.css` and `e2e/project-tree-actions.spec.ts` were deleted. The rejected implementation, tests and diff were not read.
`playwright.project-tree-actions.config.ts` was kept unchanged (port 8742, `scripts.serve_clean_editor_fixture:create_fixture`).

Raw logs (command, SHA256 of owned files, UTC timestamps, true exit, full output):
`C:/Users/Admin/AppData/Local/hermes/handoffs/canvas-orchestration/desktop-v3/project-tree-vertical/*.log`, written by `run.py` in that directory.

## Slices done (each: one new test → functional RED on the previous build → minimum code → rebuild → GREEN)

1. **Toolbar expands known folders** (V3-PRJ-003). Button „Rozbalit src, backend, tests“ in the Strom group.
   - Code: optional `expandKnown` counter prop on SourceExplorer. It expands only directory entries already returned for the root page, named src/backend/tests, not blocked, and not when `rootOnly`. Missing pages load lazily through the existing `load()`.
   - RED `20260911T072645Z-s1-red.log`: setup passed, then failed only at the missing toolbar button. GREEN `20260911T072813Z-s1-green.log`.
   - The test uses a real temp source dir with a `docs` control folder. It asserts `docs` stays collapsed, there are no non-GET requests during the action, and exactly 3 tree GETs.
2. **Collapse all stays collapsed despite an in-flight child fetch** (V3-PRJ-004). Button „Sbalit vše“.
   - Code: optional `collapseAll` counter prop that only clears `expanded`; loaded pages are kept. `load()` never touches `expanded`, so a late response cannot re-open a folder.
   - RED `20260911T072858Z-s2-red.log`: the real `src` response was held (`route.continue` after a gate, no fake data) and the test failed only at the missing button. GREEN `20260911T073024Z-s2-green.log`.
   - The test asserts: still collapsed after the late response arrives, re-expanding reuses the loaded pages (1 GET per folder), and no non-GET requests.

Other SourceExplorer consumers get no new props and keep their behaviour; the defaults are 0 (no-op).

## Not implemented (reported, not raced)
- Slice 3, clear source search / search-active note (V3-PRJ-005).
- Slice 4, focused-row keyboard Enter / ArrowRight / ArrowLeft / Ctrl+A (V3-PRJ-014).
- Slice 5, per-row „+ Editor“ via `onAdd`/`allowedReference`, with disallowed entries blocked (V3-PRJ-015).
- Slice 6, '/' focuses project source search only while ProjectWorkspace is mounted, not editing text, and no modifiers (V3-KEY-004).

## Known gaps / unverified
- The expand button stays enabled when the root has none of src/backend/tests; clicking it is then a no-op with no disabled reason shown.
- No new CSS. Toolbar fit at 1280/1920 was not screenshot-verified; the tests run at 1440 only.

## Gates (same built bytes: `20260911T073012Z-s2-green-build.log`)
- Focused: 2 passed (`20260911T073030Z-focused-all.log`).
- Full clean-editor suite: 97 passed, 1 skipped, exit 0 (`20260911T073035Z-clean-editor-full.log`).
- `tsc --noEmit`: exit 0, 499 files (`20260911T073233Z-tsc-diagnostics.log`).
- `git diff --check` on owned paths: clean.
- No merge, push, preview 8780, backend or global changes.
