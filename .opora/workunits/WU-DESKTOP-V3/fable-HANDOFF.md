# fable-HANDOFF — BACKEND lane WU-DESKTOP-V3

Worktree: `C:/Users/Admin/opora-v3-fable`, branch `feat/desktop-v3-fable`.
Parent baseline: `bf8a1767ae098433dd6f5ee61a08602d8713b193`.
Design source verified: sha256 `541cb172c681e2e9745ad4da2259a8db10bbab144c46271fb61b83c186428bce` (118428 B). Treated as untrusted design data; no prototype dummy data copied.

## Commit

`f214771` — feat(desktop-v3): revisioned project memory, complete agent packets, snapshot handoff prepare
(a follow-up commit adds only this handoff file).

## OWNED / CHANGED PATHS

New:
- `backend/desktop_v3_state.py` — State store + strict validation + phase gate.
- `backend/desktop_v3_packets.py` — shared assembly (`drawing_chain`, `memory_for`, `project_drawing`), `DesktopV3Packets` (preview / snapshot / load / current_digest).
- `backend/desktop_v3_routes.py` — `/api/desktop-v3/*` router.
- `tests/test_desktop_v3_state.py`, `tests/test_desktop_v3_packets.py`, `tests/test_desktop_v3_prepare.py`.

Modified:
- `backend/app.py` — wires `DesktopV3State`, `DesktopV3Packets`, router; sets `handoffs.desktop_v3`.
- `backend/planning_context.py` — adds `drawings` (node + ancestors + root) and `memory` from the shared assembly; all original keys unchanged.
- `backend/task_handoffs.py` — `prepare_from_snapshot`, `_snapshot_context`, `_check_sources`, `_check_context`; existing prepare/start/stop/export/list/get untouched in behaviour (start guards refactored into the two helpers, same errors for the old packet kind).

No frontend, package manifest, lockfile, CONTRACT, production data or server was touched.

## API delivered (matches CONTRACT "Společné API")

- `GET /api/desktop-v3/state?project&workspace` → `{revision, state, readOnly}`; defaults are empty arrays/objects, no demo data; main → `readOnly:true`.
- `POST /api/desktop-v3/state {project, workspace, expectedRevision, state}` → same shape. Strict key/enum/limit validation (409), CAS 409 on revision mismatch, main 409, `BEGIN IMMEDIATE` atomic write, reload persists. Phase forward (`discover→define→build→verify→live`) requires non-empty and all-checked criteria on the node; backward/same is free. Saving state touches no run store.
- `POST /api/desktop-v3/packet/preview {project, workspace, nodeId, path, sessionId, references, note}` → `{digest, packet}`.
- `POST /api/desktop-v3/packet/snapshot {…same…, digest}` → `{id, digest, packet, createdAt}`; rebuilt and compared, 409 when sources changed since preview.
- `GET /api/desktop-v3/packet/snapshots/{id}?project&workspace` → immutable stored snapshot; 409 for other scope/missing.
- `POST /api/desktop-v3/packet/snapshots/{id}/prepare {project, workspace, task}` → existing `TaskHandoffs` public record (`status:"prepared"`, `events:[]`, no pid, no workspace dir). `context.documents` IS the snapshot packet (the bytes the worker tool `canvas_read_document_context` serves). Existing `/api/task-handoffs/{id}/start|stop|export` are reused; start requires exact digest + confirmed, re-verifies snapshot digest against a fresh assembly and the context digest, keeps main/timeout/single-run guards, refuses when Hermes runtime is absent.

Packet (`opora.packet/1`): `scope`, `task` (node summary, sourceRef, path, note, references as `contentIncluded:false`, spec, text, phase/criteria/steps), `context` (project, projectSettings, memory {revision, settings, scoped rules/decisions/tickets}, graph digest, ancestors, children, relations, texts, specs, drawings, documents, journal, excluded), `sourceManifest[{kind, ownerId, revision, included, reason}]`, `warnings`, `policy {autostart:false, requiresConfirmation:true, provider:null, proposalOnly:true}`, `report`.

Critical fix: `drawings` covers focus, every ancestor and the root layer; each with its own revision; deleted elements filtered; arrow `points`/`startBinding`/`endBinding` and bound-text labels preserved. An empty focus drawing is manifest `included:false, reason:no_saved_drawing` while the parent's rev1 scene is included. Limit (`MAX_PACKET_BYTES`=900000): mandatory core exceeding → explicit 409; optional sources dropped → manifest `limit_exceeded` + warning, never silent. All strings pass `redact_text` (deep).

## RED → GREEN evidence (real runs in this worktree)

Baseline before changes:
```
uv sync && uv run pytest -q -x --no-header -p no:cacheprovider
265 passed, 4 skipped, 2 warnings in 124.94s   (exit 0)
```
RED (tests written first, modules absent):
```
uv run pytest -q --no-header -p no:cacheprovider tests/test_desktop_v3_state.py
30 failed, 2 warnings in 18.69s   (exit 1)
uv run pytest -q --no-header -p no:cacheprovider tests/test_desktop_v3_packets.py
ImportError: cannot import name 'desktop_v3_packets' from 'backend'   (collection error, exit 2)
tests/test_desktop_v3_prepare.py — same collection error
```
GREEN after implementation:
```
uv run pytest -q --no-header -p no:cacheprovider tests/test_desktop_v3_state.py tests/test_desktop_v3_packets.py tests/test_desktop_v3_prepare.py
42 passed, 2 warnings in 27.02s   (exit 0)
uv run pytest -q --no-header -p no:cacheprovider
307 passed, 4 skipped, 2 warnings in 146.15s   (exit 0)   ← full existing regression + new
uv run ruff check <changed files>
All checks passed!   (exit 0)
```

## Verified behaviour (by the 42 tests)

State: default empty; save/reload exact; CAS 409 keeps stored state; project/workspace isolation; 23 malformed payload/rule/path/enum cases rejected without persisting; phase gate forward/backward; criteria save leaves llm/coding/handoff runs, graph digest and node spec untouched; main read-only GET/POST.

Packets: ancestor drawing rev1 with 30 active elements, arrow geometry, labels, deleted filtered, focus rev0 not marked loaded; rules scoped by project/path-prefix/node lineage; decisions pinned or node/path-scoped; tickets by node/session; documents by path/sourceRef/root; references never read (source file contents and absolute paths absent from packet); secrets in memory and drawing text redacted; digest deterministic and changes with ancestor drawing/note; snapshot digest match/409 stale/immutable after change/scope isolation; scope validation and concept without path; missing path → manifest `not_found` + warning; byte limit explicit; planning `/api/llm/preview` exposes identical `drawings[parent].elements` and the same scoped `memory.rules`.

Prepare: existing public format; `readableNodeIds` = lineage; `contextSummary` carries snapshotId/packetDigest/sourceManifest; export `context.documents == snapshot.packet`; `DocumentTools.read_context("documents")` returns the same packet; `_initialize_workspace` writes `handoff-context.json` whose `context.documents` canonical bytes equal the snapshot; no workspace/run dir created by prepare; wrong digest / unconfirmed / other-scope / bad task / missing snapshot → 409; state change after snapshot → start 409 "změn…", record stays `prepared`, snapshot unchanged.

## Limitations / notes for coordinator

- No live Hermes run was executed (no runtime in this worktree, by design); start path was verified up to the guard that refuses without Hermes. Existing runtime behaviour after `starting` is unchanged code.
- `nodes`/`tickets`/`decisions` nodeIds are validated for format, not graph membership, so deleting a graph node never makes the memory unsaveable; packets report lineage from the live graph.
- Node-scoped rules/decisions apply to the focus node and its ancestors (sector rules reach children). Path rules use prefix match on the request path and the focus sourceRef path.
- Planning context (`/api/llm/preview`) gains `drawings` + `memory`; the existing 50000-char planning cap in `llm_runs` still applies and fails explicitly, never truncates.
- Journal entries: latest 7 days of the focus node are included.
- UI-side items (panels, confirmation flow) belong to Sonnet/Opus lanes; `handoffs.desktop_v3` must stay wired in `app.py` for v3 starts.
- No push, no merge, no server restart, no production data touched.
