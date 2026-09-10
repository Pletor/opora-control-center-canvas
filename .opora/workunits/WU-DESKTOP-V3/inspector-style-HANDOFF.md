# Inspector style boundary — HANDOFF

Branch `fix/v3-inspector-css-boundary` (base `a3832dc`), worktree `C:/Users/Admin/opora-v3-inspector`.

## Symptom (user: „Inspektor má rozbitý layout když není aktivovaný wireframe")
In drawing mode with Wireframe OFF and a shape selected, the native Excalidraw selected-shape
inspector (`.excalidraw .App-menu__left`) was malformed: color swatches rendered as 17.5×32 px
rectangles, the opacity range was drawn as a padded 32 px field, and the lower sections ("Vrstvy")
got clipped. The right-hand OPORA shell was not the cause and was not resized.

## Root cause (verified via computed styles)
Generic tag rules in `src/style.css` (`button`, `input/select/textarea`, `:hover`, `:disabled`,
`:focus-visible`, `h1–h4/p/dl`, `h2/h3/h4`, `code/kbd`) applied inside the vendor subtree. Measured
on the RED run: `.color-picker__button` computed `min-height: 32px`, box 17.546875×32. Excalidraw
0.18.1 natively sizes it at 1.35rem square and the `.range-input` track at 4 px tall. The OPORA `h3`
rule also uppercased the native "Obrys/Pozadí" labels and added margins.

## Fix (`src/style.css` only)
Each of those rules is now scoped `tag:not(:where(.excalidraw *))`. `:where()` contributes zero
specificity, so every OPORA selector keeps its original specificity (for example `button` stays
(0,0,1)), and class-level OPORA overrides such as `.topbar-select` and `.drawing-tools button`
still win as before. There's no vendor reset, no hidden native inspector, Wireframe isn't forced,
and no data, node IDs or components change. The `font: inherit; color: inherit` reset is unchanged.
`src/drawing.css` didn't need changes because its rules are class-scoped to OPORA containers.
Excalidraw's color popover (`.color-picker-content`) renders inside `.excalidraw`, so the same
boundary covers it (the test asserts this).

## Test (`e2e/inspector-style-boundary.spec.ts`, new)
It runs on the fixture server on port 8742. The test draws its own rectangle in the fixture draft
project and doesn't save it. It blocks external requests and makes no model or backend calls. For
1280 and 1440 widths × light and dark themes, with Wireframe off→on→off, it checks that:
- native swatches are square, under 28 px, and have no 32 px min-height
- the native range is at most 8 px tall, with no 32 px min-height, no `7px 9px` padding and no border
- native sections don't overlap, the panel stays inside the Excalidraw host, and its content can be reached
- the color popover is inside `.excalidraw` with square swatches
- the OPORA controls "Uložit kresbu" and "Nástroj: Obdélník" keep 32 px min-height and height, and the top-bar select keeps its 1 px OPORA border, non-zero radius and ≥30 px height

The graph digest stays unchanged and there are no page errors.

## Commands and exact results
Build: `npm run build` (runs `tsc --noEmit` + vite build), then `dist` is copied to `.data/clean-editor-dist`.
Test: `npx playwright test --config playwright.clean-editor.config.ts e2e/inspector-style-boundary.spec.ts --project=legacy --reporter=list`

RED (original CSS), 2 failed:
```
x  1 [legacy] › e2e\inspector-style-boundary.spec.ts:101:3 › native drawing inspector keeps vendor layout without Wireframe at 1280px
x  2 [legacy] › e2e\inspector-style-boundary.spec.ts:101:3 › native drawing inspector keeps vendor layout without Wireframe at 1440px
Error: 1280 Světlý wireframe off: square swatch {"w":17.546875,"h":32,"minHeight":"32px","padding":"0px"}
Expected: <= 1
Received:    14.453125
```
GREEN (fixed CSS):
```
ok 1 [legacy] › e2e\inspector-style-boundary.spec.ts:107:3 › native drawing inspector keeps vendor layout without Wireframe at 1280px (1.7s)
ok 2 [legacy] › e2e\inspector-style-boundary.spec.ts:107:3 › native drawing inspector keeps vendor layout without Wireframe at 1440px (1.6s)
2 passed (12.7s)
```
`npx tsc --noEmit` → exit 0.

Two intermediate runs after the fix failed on bad test assumptions, not on product behavior. The
assertions expected the top-bar select to have 32 px height and `7px 9px` padding, but the
pre-existing `.topbar-select` rule sets 30 px and `4px 8px` by design. The assertion was corrected
to check the generic OPORA border instead.

## Not done / for coordinator
- No full-suite run (the coordinator owns it). Only the focused spec was run.
- Evidence screenshots `evidence/inspector-style-boundary-{1280,1440}.png` were written by the test and left uncommitted.
- No comparison against the running preview on port 8780 was needed. The bug reproduced on the private fixture.
