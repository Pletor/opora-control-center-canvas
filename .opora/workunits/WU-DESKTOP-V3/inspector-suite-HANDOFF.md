# Inspector suite isolation — handoff (2026-09-11)

Branch `fix/v3-inspector-suite-isolation`. No product CSS/source change.

## Cause
Full regression (`clean-editor.log`): both inspector cases expected `drawing-element-count` 1, received 2.
`e2e/drawing.spec.ts` saves a rectangle to the shared `draft/draft/root` drawing before this spec runs; `drawRectangle` assumed an empty scene. Test setup issue, not a product regression.
The earlier private-port attempt failed with `net::ERR_FAILED` only because the spec hardcoded the external-origin allowlist to `http://127.0.0.1:8742`.

## Fix (`e2e/inspector-style-boundary.spec.ts`)
- The allowed origin comes from the test `baseURL`. Every other HTTP origin is still aborted and asserted empty.
- Only `GET /api/drawing?project=draft&workspace=draft&layer=` is intercepted. The spec takes the real server response (`route.fetch`) and fulfills it with `scene.elements = []`, keeping the real shape, revision and source.
- Any non-GET `/api/drawing` is aborted and asserted absent.
- New assertions: the isolated read was used; the stored drawing (read via `page.request`, which bypasses `page.route`) keeps the same revision and scene before and after.
- Unchanged: both widths, light/dark themes, Wireframe off→on→off, palette/slider/popover/OPORA controls, graph digest, no page errors, no external network.
- Reproduction switches: `OPORA_INSPECTOR_SEED=1` saves a valid rectangle, but only if the root drawing is empty (same-origin JSON POST with `expected_revision` from GET). `OPORA_INSPECTOR_UNISOLATED=1` disables the intercept (RED only).

## Private config (`playwright.inspector-suite.config.ts`)
Port 8795, temp data dir, clean-editor dist, `testMatch` limited to the owned spec.

## Verification (port 8795, fresh temp DB per run)
- RED `OPORA_INSPECTOR_SEED=1 OPORA_INSPECTOR_UNISOLATED=1 npx playwright test -c playwright.inspector-suite.config.ts`: 2 failed, `Expected "1" Received "2"` at `drawRectangle`. Same failure as full regression.
- GREEN `OPORA_INSPECTOR_SEED=1 npx playwright test -c playwright.inspector-suite.config.ts`: 2 passed, persisted seeded scene unchanged.
- GREEN without seed: 2 passed.
- `npx tsc --noEmit` passes; standalone strict tsc of spec+config passes; `git diff --check` clean.
- Not run: full shared regression on 8742 (out of scope/access).
- Uncommitted artifacts: `evidence/inspector-style-boundary-{1280,1440}.png`, produced by the test.
