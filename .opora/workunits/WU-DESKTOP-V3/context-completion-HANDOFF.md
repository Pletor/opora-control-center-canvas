# WU-DESKTOP-V3 — context completion lane (Claude Code Opus 5) — HANDOFF

- Base: `826d30b` · branch `fix/v3-context-completion` · worktree `C:/Users/Admin/opora-v3-context`
- Implementation commit: `78d086b14c72de617e616b84e4f8eab8cb969662`
- Status: **DONE — coordinator verified**

## Changed paths
- `backend/desktop_v3_packets.py` — `DesktopV3Packets._session()` + wiring in `_assemble()`.
- `tests/test_desktop_v3_packets.py` — seed fixture revised, 4 new vertical tests.
- `.opora/workunits/WU-DESKTOP-V3/context-completion-HANDOFF.md` — this file.
- Unchanged (not needed): `backend/task_handoffs.py`, `backend/desktop_v3_routes.py`, `tests/test_v3_acceptance.py`, `tests/test_desktop_v3_prepare.py`, `tests/test_desktop_v3_state.py`. No frontend change.

## Behavior
- `sessionId` in `opora.packet/1` now resolves to a **real stored session** from the local stores only:
  1. `llm_runs` (local planning run) → `context.session.kind = "planning_run"`, manifest reason `saved_planning_run`;
  2. `task_handoffs` (documentation handoff) → `kind = "documentation_handoff"`, reason `saved_documentation_handoff`.
- `context.session` = `{id, kind, nodeId, status, message, task, output, error, createdAt, updatedAt, proposalOnly: true}`.
  Handoff: `output` = `result.content` or `null`; its stored context/packet is **not** copied in. Planning: `output` = saved output or `null`.
- One `sourceManifest` row `{kind:"session", ownerId:<sessionId>, revision:null, included:true, reason}`.
- Redaction: the whole packet goes through `redact_deep` (session output/task/message included).
- 409 (same message, no content leak) for unknown id, an id only present in project memory (ticket `sessionId`), another project, or another workspace. The check runs before anything else is assembled, and preview, snapshot and `current_digest` (handoff start) all use the same `_assemble`.
- The digest covers status/output/updatedAt, so a changed session output → new preview digest, old-digest snapshot 409, a prepared handoff over the old snapshot refuses start (409, stays `prepared`). The stored snapshot stays immutable.
- Empty `sessionId`: no `context.session` key and no session manifest row, so the digests of existing session-less snapshots don't change.
- Session is a mandatory source (both stores cap output at 64 KB); if it doesn't fit, `MAX_PACKET_BYTES` gives an explicit 409. It is never dropped silently.
- No arbitrary filesystem read, no new file read grant, no graph node invented for project/path scope, no model start on preview/snapshot/prepare. Ancestor drawings are unchanged.

## Fixture revision
- `seed()` in `tests/test_desktop_v3_packets.py` used `sessionId="sess1"` with no stored session. It now stores a real completed `llm_runs` row `sess1` (project/draft, layer `focus`, output containing a fake key) via the new `store_planning_run()` helper. No security or acceptance assertion was weakened; ticket scoping `t1,t2` is unchanged.

## RED → GREEN
- Start: `uv run pytest tests/test_v3_acceptance.py -q` → 1 failed, 2 passed (`KeyError: 'session'` in `test_session_packet_contains_real_scoped_proposal_output`).
- RED after adding tests: `uv run pytest tests/test_desktop_v3_packets.py tests/test_desktop_v3_prepare.py tests/test_v3_acceptance.py -q` → 5 failed, 14 passed:
  - `test_session_scope_includes_the_real_stored_planning_run_redacted_with_manifest` (KeyError session)
  - `test_session_scope_rejects_memory_only_unknown_cross_project_and_cross_workspace_ids` (200 != 409 for memory-only `other`)
  - `test_session_output_change_changes_digest_and_blocks_stale_snapshot_start` (KeyError session)
  - `test_prepared_documentation_handoff_is_a_real_session_and_its_result_changes_digest` (KeyError session)
  - `test_v3_acceptance.py::test_session_packet_contains_real_scoped_proposal_output` (KeyError session)
- GREEN: `uv run pytest tests/test_desktop_v3_packets.py tests/test_desktop_v3_prepare.py tests/test_desktop_v3_state.py tests/test_v3_acceptance.py -q` → 49 passed.
- `uv run ruff check backend/desktop_v3_packets.py tests/test_desktop_v3_packets.py tests/test_v3_acceptance.py` → All checks passed.
- Full backend suite `uv run pytest tests -q` → **314 passed, 4 skipped**, two existing dependency deprecations, exit0, 146.38s. Coordinator executed this after proving the Opus process tree inactive: the lane exited before finishing its own background full-suite run, so that abandoned run is not counted.
- Independent Claude Code Opus static review: passed=true, security_concerns=[], logic_errors=[]. Evidence: `C:/Users/Admin/AppData/Local/hermes/handoffs/canvas-orchestration/desktop-v3/context-review.json`. Robustness/test suggestions remain non-blocking; no live model invocation claimed.

## Limits / notes for coordinator and frontend
- Frontend should treat `packet.context.session` as optional (absent when `sessionId === ""`).
- A session from any node in the same project/workspace is accepted (its `nodeId` is exposed). Project+workspace is the security boundary; it is not restricted to the request's lineage.
- Memory ticket `sessionId` values are still stored unvalidated by `desktop_v3_state` (not an exclusive file here). They only filter tickets when the packet's session is real.
- Handoff session `updatedAt` changes on every event/status save, so any handoff activity invalidates dependent snapshots. This is intentional (content change detection).
- Old snapshots that carried a non-empty invented `sessionId` now fail `current_digest` with 409 at start. That's intended: they never referred to a real session.
- Not done: no live server, browser, or real model/API run (per lane rules).
