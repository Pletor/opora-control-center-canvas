# Packet scope recovery — HANDOFF

Scope (exclusive writes): `src/desktop-v3/AgentPacketPanel.tsx`,
`e2e-v3-panels/agent-packet.spec.ts`, this file. No other paths touched.

## Bug
Changing scope (node/path/session/etc.) while `buildPreview()` was in flight bumped
`generation.current` to invalidate the stale response, but never reset `busy`. The stale
request's own `finally` checks `ticket !== generation.current` and skips `setBusy(false)`, so
nothing was left to ever clear `busy` — the "Sestavit náhled balíčku" button stayed disabled
forever and the new scope could never be built.

Separately, "Exportovat přesné zadání" captured `run` by closure but had no ticket/generation
check at all: if scope changed while the export request was pending, the old run's response
would still download and, on failure, `setError` would land in the already-reset new scope.

## Fix (`AgentPacketPanel.tsx`)
- Scope-change effect now also calls `setBusy(false)` — the new scope always starts idle; a
  late stale response can't re-flip `busy` because its ticket no longer matches.
- Export `onClick` now captures `ticket = generation.current` and the target run before the
  `await`, and after it resolves, checks `mounted.current && ticket === generation.current`
  before doing anything — skips both the download and `setError` if scope changed meanwhile. It
  also now checks `value.digest === exportedRun.digest` in addition to matching `id`.

## Tests (`agent-packet.spec.ts`)
Two new gated (deterministic, no fixed-timeout races) tests, following the existing
`gate`/`release` Promise pattern used in `live-desktop.spec.ts`:
- "scope change while a preview is pending recovers busy and can build the new scope" — gates
  node-a's preview response, switches to node-b mid-flight, asserts the build button re-enables
  and a new node-b preview builds successfully, then releases the stale node-a response and
  confirms it doesn't disturb node-b's preview.
- "switching scope while exporting a run does not download stale data or leak an error into the
  new scope" — drives a real run to "Běží", gates the export response, switches scope mid-flight,
  releases, and asserts no `download` event fired and no `alert` role appeared.

Both were confirmed RED against the pre-fix source (temporarily set aside via
`git stash push -u`, then reapplied and dropped — no other worktree's stash entries touched) and
GREEN after the fix, alongside the 4 pre-existing tests in the file (6/6 total).

## Verification
- `npx tsc --noEmit` — clean.
- `npx playwright test --config playwright.desktop-v3.config.ts e2e-v3-panels/agent-packet.spec.ts --reporter=list`
  — 6 passed.

## Limits
- Did not touch active-run poll/stop logic, snapshot/reload logic, or any other panel/file —
  only the two spots above.
- No model/API startup, no push/reset/clean, no edits outside the three owned paths.
