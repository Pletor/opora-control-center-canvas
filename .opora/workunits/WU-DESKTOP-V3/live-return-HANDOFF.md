# Live Run return-navigation — candidate handoff (Opus, fix/v3-live-view-return)

Status: CANDIDATE. Not reviewed, not merged, not published. Does not claim the full GOAL.
Base: 2756eeeb4445ceda9f0173014aabf92871cae585. Owned paths only: `src/desktop-v3.css`,
`e2e/live-view-return.spec.ts`, `playwright.live-return.config.ts`, this file.

## Root cause (product)
`src/workspace-modes.css` `.agents-mode .agents-workspace { position:absolute; inset:0 }`.
In v3 `App.tsx` renders `.v3-live` (flex column) = `nav.v3-live-tabs` + direct `<AgentsWorkspace>`.
Nearest positioned ancestor is the canvas surface, so the absolute `section.agents-workspace`
covered the tabs after switching to "Dohled běhů"; a normal click on "Přehled a tickety" was
intercepted by `<strong>Live Run</strong>` from that section (same as coordinator's preview evidence).

## Fix
`src/desktop-v3.css`: `.agents-mode .v3-live > .agents-workspace { position: relative; inset: auto; }`
(specificity 0,3,0 > 0,2,0). The viewer becomes the existing `.v3-live > :last-child` flex child
(flex:1, min-height:0, overflow:auto) under the tabs. Non-v3 path (AgentsWorkspace not inside
`.v3-live`) is untouched; the advanced viewer is not hidden.

## Setup root cause (prior wasted run)
Owned config used `backend.app:create_app` (serves absent `dist/`). Now uses
`scripts.serve_clean_editor_fixture:create_fixture` (serves `.data/clean-editor-dist`), port 8742,
unique `.data/e2e-live-return-<stamp>` data root, `reuseExistingServer:false`. No font copy was needed.
`.data` verified not a reparse point (fsutil exit 1) before build writes.

## Evidence (raw logs in E/live-return-recovery, E = hermes handoffs canvas-orchestration/desktop-v3)
- `red-run.log`: private build exit 0; targeted spec exit 1 on unchanged CSS — `overviewTab.click()`
  (spec line 24) timed out, "<strong>Live Run</strong> from <section aria-label="Agenti"
  class="agents-workspace"> subtree intercepts pointer events". Region/button names were verified
  against source first (`Live workspace`, `Agenti`, `Nástroje Live Run`), so this is product RED, not setup.
- `green-run.log`: rebuild exit 0; targeted spec `--repeat-each=2` → 2 passed, exit 0
  (1280/1440/1920, two round trips each, normal clicks only, `.live-columns` no horizontal overflow,
  zero non-GET `/api/` requests, toolbar "Nástroje Live Run" visible).
- `full-clean-editor.log`: `playwright.clean-editor.config.ts` → 95 passed, 1 skipped, exit 0.
  Skipped = existing explicit `LIVE: UI to Hermes…` in `e2e/coding.spec.ts` — skipped, NOT acceptance.
- `tsc-diffcheck.log`: `tsc --noEmit` exit 0; `git diff --check` exit 0.

## Warnings / limitations
- No force click, dispatchEvent, JS click or reload used. No model start, no Docker, no 8780/8768/8740.
- "Advanced tools usable" is proven only as toolbar visibility plus tab switching; individual
  advanced tool actions were not clicked in this spec (they would start runs/writes).
- No geometry assertion added to the spec; the normal-click interception is the regression signal.
- Published preview (8780) not rechecked by this lane; coordinator reads it back.
