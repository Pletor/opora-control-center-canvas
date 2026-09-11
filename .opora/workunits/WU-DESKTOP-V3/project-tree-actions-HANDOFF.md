# WU-DESKTOP-V3 — Project tree actions — CANDIDATE handoff

State: **CANDIDATE** for reviewer. This is not a claim that the whole desktop-v3 GOAL is done; reviewer decides acceptance.

- Worktree: `C:/Users/Admin/opora-v3-project-tree`, branch `feat/v3-project-tree-actions`, base HEAD `959f879bded3e711b414c9f4e61564608160d8a6`.
- Evidence logs (raw output + meta with the real subprocess exit code, source hashes and dist hash, written by `run.py` with no pipeline):
  `C:/Users/Admin/AppData/Local/hermes/handoffs/canvas-orchestration/desktop-v3/project-tree-actions/NN-name.{raw.log,meta.json}`.
- No integration, no push, no backend/DB/source repository writes, no model start, no filesystem rights changes.
  Original `P:/main`, ports 8768/8740 and preview 8780 were not touched. Tests used only 8742/8769/8771.

## Scope — 6 actions

| # | Action | Implementation | Test (e2e/project-tree-actions.spec.ts) |
|---|--------|----------------|------------------------------------------|
| 1 | Bulk expand of **loaded** `src`/`backend`/`tests` only | `SourceExplorerHandle.expandKnown(names)` — only direct, already-loaded, non-blocked root directories matching the names; one level, no recursion, no invented paths; no-op under `rootOnly`. Toolbar button "Rozbalit src · backend · tests"; status note when none are loaded. | `:29` bulk expand — `src/nested` stays collapsed (`deep.py` count 0), `docs` untouched, zero non-GET requests, toolbar overflow ≤1px at 1280/1440/1920 |
| 2 | Collapse all | `collapseAll()` clears `expanded`; loaded pages stay cached; a late in-flight response does not reopen the folder. Toolbar button "Sbalit vše". | `:57` — held `backend` response released after collapse stays collapsed; `src` re-expand reuses cache (`srcRequests === 1`) |
| 3 | Clear search | `onClearSearch` → note "Hledání „…“ prochází jen načtené složky." with a "Zrušit" button; clears search only. | `:57` (second half) — input empty, note gone, open tree stays open |
| 4 | Row keyboard | `rowKey` on the row name button: ArrowRight opens / ArrowLeft closes a directory; Enter = native button select; Ctrl/Cmd+A adds a referenceable row to Editor context. Ignored with Shift/Alt, on non-row targets and in editable fields. | `:103` — Arrow expand/collapse, Enter opens `src/main.py`, Ctrl+A adds exactly one `src/main.py`; Ctrl+A inside search input adds nothing |
| 5 | Per-row `+ Editor` | Button per row when `onAddReference` is set; adds that row's path without changing selection; disabled for link/blocked/sensitive/technical paths (`allowedReference`). Scoped CSS in `src/project-tree-actions.css`. | `:136` — selection stays `src`, `backend` in shelf once, button inside row box, no horizontal tree overflow, `node_modules` row button disabled |
| 6 | `/` focuses search | Window `keydown` listener in `ProjectWorkspace`; skipped for modified keys, `defaultPrevented`, editable targets (`input, textarea, select, [contenteditable]`) and open modal dialogs; unregisters on unmount. | `:166` — focus from neutral heading; `/` typed into "Podstata" stays text; no Project toolbar in Editor; works again after returning to Projekt |

## Final bytes (sha256, verified against current worktree and 19/20/21 meta)

| Path | sha256 |
|------|--------|
| `src/SourceExplorer.tsx` | `c944915b59b901a45aae09f39943bbbdd4152e49a0cdf6d0406db7ee5ce1aefb` |
| `src/ProjectWorkspace.tsx` | `6c98f4c92be644336fa106ff68071cf90e397d3a0f8fc0df44ee6d30c219c647` |
| `src/project-tree-actions.css` | `ce33ca9f10678a0a361fba5fa252f1f954744a9b7fd934064b4fdba1060058f9` |
| `e2e/project-tree-actions.spec.ts` | `6332d16d447c4752ad69905cef4364ac19585337c256d478d36f9dc5b67d2bac` |
| `playwright.project-tree-actions.config.ts` | `083a5cf3f412a2f9b139aa5c65fb5d65f2c986f9c48638890a2ebe4be6ff5148` |

Isolated build `.data/clean-editor-dist` sha256 `6eb319373666fb44a20f66489062fb5324606f89abd9abb567dd9ab74cf6b5c3` — produced by `11-build-final` (exit 0) from exactly the three product hashes above. Only the spec changed after that build (spec is not bundled). This completion lane did not rebuild or delete `.data`.

## Gates

| Log | Command | Result |
|-----|---------|--------|
| `17-focused-all-final` | `node node_modules/@playwright/test/cli.js test -c playwright.project-tree-actions.config.ts --reporter=list` | exit 0 — 5 passed, 0 skipped (6.5s), port 8742 |
| `19-completion-full` | `node node_modules/@playwright/test/cli.js test -c playwright.clean-editor.config.ts --reporter=list` | exit 0 — 101 tests: **100 passed, 1 skipped**, 0 failed, 0 flaky (1.4m / 87.2s), ports 8742/8769/8771; includes all 5 project-tree tests (#48–#52) |
| `20-completion-tsc` | `node node_modules/typescript/bin/tsc --noEmit` | exit 0, empty output (0.4s). `--listFilesOnly` confirms the program includes `src/SourceExplorer.tsx`, `src/ProjectWorkspace.tsx`, `e2e/project-tree-actions.spec.ts` |
| `21-completion-diff-check` | `git diff --check` | exit 0, empty; additionally `git diff --cached --check` on the 5 code paths exit 0 |

- Skip: `e2e/coding.spec.ts:15` "LIVE: UI to Hermes to isolated repo to independent Docker tests" (pre-existing live-only skip, unrelated to this slice).
- Warnings: none matched `warn` in the 19 raw log.
- `18-clean-editor-full.raw.log` is **INTERRUPTED** (stopped at test 58 at the previous lane's 720s deadline; no meta, no exit, no summary). NOT PASS. Kept intact (sha256 `41f3ae279efee89adbbad38bf624c498200e80f0f213251b4f0d36c968810fb8`); superseded by 19.
- Earlier `14-tsc` / `15-diff-check` ran against the intermediate spec `5d64bb…`; 20/21 re-run them against the final spec `6332d1…`.

## TDD disclosure (ordering as it actually happened)

1. The recovery started from restored, unmodified product source plus the **existing** tests from the interrupted previous lane. They were not newly written in this recovery.
2. `02-red-baseline-all5` (product `5104a0…`/`5b3227…`, no CSS, spec `8bde0b…`): true **exit 1**, all 5 failing on behaviour — missing bulk button (timeout), missing "Sbalit vše" (timeout), ArrowRight did not expand, missing `+ Editor` (timeout), `/` did not focus search.
3. After that, slices went in with a separate build and a separate GREEN run for each: 03→04 bulk (exit 0), 05→06 collapse/clear search (exit 0), 07→08 keyboard (exit 0), 09→10 row add + CSS (exit 0), 11→12/16 slash.
4. The spec changed during the slices (hashes `8bde0b…` → `7a6580…` between 02 and 04, `7a6580…` → `5d64bb…` between 08 and 10, `5d64bb…` → `6332d1…` between 12 and 16). Line-number shifts suggest these were extra assertions (e.g. the toolbar overflow check and the `+ Editor` containment and disabled checks), but this lane did not keep the old bytes. The reviewer should diff them from the previous lane's `events.jsonl`. This lane does **not** claim an independently authored, new-test RED run for each slice. The only RED evidence is the all-5 baseline.
5. Slash, in detail: `12-green-slice5-slash` failed (exit 1) with the final product source `6c98f4…` because the test's `page.locator("body").click()` lands in the document editor, and `/` inside an editable field is correctly ignored by design. That is a **test precondition problem, not a product defect**. The test was changed to click the non-editable heading "Strom projektu" for the Projekt-side focus steps (comment at spec line 170). Assertions were not weakened: the `toBeFocused`, `/` typed into "Podstata" and toolbar-absence checks stay the same. The product was unchanged between 12 and 16 (same `6c98f4…`). `16` passed, exit 0.

## Before / after evidence

- Before: `02-red-baseline-all5.raw.log` (5 failed, exit 1).
- After: `17-focused-all-final.raw.log` (5 passed), `19-completion-full.raw.log` (100 passed / 1 skipped), `20-completion-tsc`, `21-completion-diff-check`.
- This spec produces no screenshots. The dirty `evidence/*.png` files in the worktree were regenerated by other suites and are not part of this commit.

## Unresolved findings / notes for the reviewer

- `playwright.project-tree-actions.config.ts` is outside the tsconfig `include` (only `playwright.config.ts`), so `tsc` does not type-check it. Playwright loads it successfully in 17.
- Bulk expand is intentionally limited to root entries that are already loaded. If the root page is still loading or the names are missing, the toolbar shows a status note instead of fetching.
- Ctrl/Cmd+A on a row name overrides the browser's select-all only while that row button has focus. Editable fields keep native behaviour (covered by the test).
- The spec diffs between intermediate hashes (see TDD point 4) have not been re-verified in this lane.
- Process state after the gates: no process with a command line matching this worktree or the fixture server, ports 8742/8769/8771 only in TimeWait (no listener), PIDs 44288/64324 absent.
