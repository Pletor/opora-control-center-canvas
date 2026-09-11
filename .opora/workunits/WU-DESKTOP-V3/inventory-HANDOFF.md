# inventory HANDOFF: WU-DESKTOP-V3 component audit (bounded completion)

- **Scope:** I edited only `component-inventory.json`, `COMPONENT-INVENTORY.md` and this file.
- **Not done:** no production or test edits, no test runners, no ports, no integration or `P:` mutations. No model started; `claude --help` was the only CLI call. OAuth/Max unchanged.
- **Base:** `a0b2c5c`. The previous Opus lane stopped at its 720 s deadline, not on quota; its 125 rows are preserved.
- Summary and counts are in `COMPONENT-INVENTORY.md`. Source hashes, coverage, `phase1Chain`, `statusCounts` and `testExecution` are also in the JSON.

## Reproduce coverage
Extract the script from this file and run it (Git Bash, from the worktree root):
```sh
sed -n '/^```js v3cov.cjs$/,/^```$/p' .opora/workunits/WU-DESKTOP-V3/inventory-HANDOFF.md | sed '1d;$d' > "$TEMP/v3cov.cjs"
node "$TEMP/v3cov.cjs" "C:/Users/Admin/AppData/Local/hermes/handoffs/canvas-orchestration/desktop-v3/06 OPORA Desktop v3.dc.html" .opora/workunits/WU-DESKTOP-V3/component-inventory.json; echo EXIT=$?
```
**Expected result:**
- 143 loose tokens = 143 occurrences, 136 unique triplets, 143 covered, 0 missing, 0 stale, 0 duplicate IDs, `EXIT=0`.
- The exit code is 1 on any duplicate ID, unmapped binding or stale ref, or if the loose and strict counts differ.

Write the script with a file tool, not a Bash heredoc: the heredoc route mangled `\\b` during this audit and produced a false 0-match run.

```js v3cov.cjs
// v3cov: reconcile every event binding in the reference HTML against component-inventory.json refs.
// usage: node v3cov.cjs <reference.html> <component-inventory.json>
const fs = require('fs');
const [src, inv] = process.argv.slice(2);
const lines = fs.readFileSync(src, 'utf8').split(/\r?\n/);
const EV = 'onClick|onInput|onChange|onKeyDown|onDragStart|onDragOver|onDragLeave|onDrop';
const strict = new RegExp('\\b(' + EV + ')\\s*=\\s*"\\{\\{\\s*([^}"]+?)\\s*\\}\\}"', 'g');
const loose = new RegExp('\\b(' + EV + ')\\b', 'g');
const occ = [];
let looseN = 0;
lines.forEach((l, i) => {
  for (const m of l.matchAll(strict)) occ.push([i + 1, m[1], m[2]]);
  looseN += (l.match(loose) || []).length;
});
const j = JSON.parse(fs.readFileSync(inv, 'utf8'));
const ids = j.rows.map(r => r.id);
const duplicateIds = ids.filter((x, i) => ids.indexOf(x) !== i);
const key = r => r.join('|');
const refMap = new Map();
for (const r of j.rows) for (const f of r.refs || []) refMap.set(key(f), (refMap.get(key(f)) || []).concat(r.id));
const occKeys = new Set(occ.map(key));
const missing = occ.filter(o => !refMap.has(key(o)));
const staleRefs = [...refMap.keys()].filter(k => !occKeys.has(k));
const multiMapped = [...refMap.entries()].filter(([k, v]) => v.length > 1 && occKeys.has(k)).map(([k, v]) => k + ' -> ' + v.join(','));
const byEvent = {};
occ.forEach(o => (byEvent[o[1]] = (byEvent[o[1]] || 0) + 1));
const statusCounts = {};
j.rows.forEach(r => (statusCounts[r.status] = (statusCounts[r.status] || 0) + 1));
console.log(JSON.stringify({
  looseEventTokens: looseN, bindingOccurrences: occ.length, uniqueLineEventBinding: occKeys.size,
  byEvent, uniqueBindingNames: new Set(occ.map(o => o[2])).size, rows: j.rows.length,
  duplicateIds, coveredOccurrences: occ.length - missing.length, missing, staleRefs, multiMapped, statusCounts,
}, null, 1));
process.exitCode = duplicateIds.length || missing.length || staleRefs.length || looseN !== occ.length ? 1 : 0;
```

## Authority applied
- **GOAL.md** (`19723aea…f76f7`) and **USER-BRIEF.md** (`1c3319f7…2b00`) are the authority for this pass:
  - Phase 1 means documentation → reviewed immutable snapshot → real agent → artifact + test results → back to the origin node and Live UI.
  - A text proposal or calculator-only coding is not enough.
- **CONTRACT.md "no general coding" is superseded.** V3-GOAL-003 is therefore now `MISSING_REPO_TRANSPORT`, meaning an implementation gap that needs runtime investigation, not an accepted blocker.
- **Repo vs. provider:** the repo lacks the routes. The installed `claude` 2.1.267 advertises `-p`, `--resume`, `--continue`, `--fork-session`, `--output-format stream-json`, `--allowedTools` and `--add-dir`. That is help text only; this audit verified no transport.
- **Phase 2:** the user supplied all 11 images. Phase 2 is waiting on phase 1 and was not implemented.

## Next two non-conflicting small TDD tasks
Neither task touches `src/api.ts`, `LiveWorkspacePanel.tsx`, `AgentPacketPanel.tsx`, `NodeWorkflowPanel.tsx`, `ProjectMemoryPanel.tsx`, the inspector test, `backend/app.py`, or the other task's files. Each is a single worktree and a single writer. Neither starts a model or opens a port.

**T1 `claude-cli-transport` (Opus)**
- **Goal:** a pure builder that turns an *approved* immutable snapshot into a scoped Claude CLI invocation, plus a capability probe. No route wiring and no process spawn.
- **Owned paths (new):** `backend/claude_cli_transport.py`, `tests/test_claude_cli_transport.py`. This name avoids the existing `tests/test_agent_transport_isolation.py`.
- **RED oracle:** `uv run pytest tests/test_claude_cli_transport.py -q` fails on a missing module. For GREEN, all of these must hold:
  - For an approved snapshot, the argv contains `-p` and `--output-format stream-json`.
  - `--add-dir` appears only for snapshot `allowedPaths` that resolve inside the workspace.
  - `--allowedTools` is an explicit list.
  - `--dangerously-skip-permissions` never appears.
  - An unapproved snapshot, a digest mismatch against `task_handoffs` canonical digest, or a `..`/absolute path escaping the workspace raises `ValueError`.
  - `capabilities()` uses only `shutil.which`. With `subprocess.run`/`Popen` monkeypatched to raise, it still returns `{"available": bool, "mode": "coding_candidate", "verified": False}`.

**T2 `agent-result-evidence` (Sonnet)**
- **Goal:** parse an agent stream-json transcript into an evidence record bound to the snapshot digest, origin node and run, so that Live Run and the node can show the real artifact and test result.
- **Owned paths (new):** `backend/agent_result_evidence.py`, `tests/test_agent_result_evidence.py`, `tests/fixtures/agent_result_evidence/*.jsonl`. Mark the fixtures SYNTHETIC; their schema must be confirmed against one real bounded run before integration.
- **RED oracle:** `uv run pytest tests/test_agent_result_evidence.py -q` fails on a missing module. For GREEN:
  - The fixture yields `{snapshotDigest, nodeId, runId, status, changedFiles, tests:{command, exitCode, passed}}`.
  - With no test result, the status is `"unverified"`, never PASS.
  - A snapshot digest mismatch is rejected.
  - Missing cost or tokens come out as `None`, not `0`.
  - `changedFiles` outside the snapshot scope set `status="scope_violation"`.

**After T1 and T2:**
- A route in `app.py`/`task_handoff_routes.py` plus explicit consent in the UI (owned by the current `AgentPacketPanel.tsx`/`api.ts` writers).
- Then one real bounded end-to-end run on the preview data copy.

## Residual gaps
- 24 MISSING rows.
- 22 PARTIAL rows.
- 16 IMPLEMENTED_UNVERIFIED rows.
- 4 MISSING_REPO_TRANSPORT rows (GOAL-001/002/003, LIVE-012).
- 2 BLOCKED_NO_TRANSPORT rows (LIVE-017 compact, LIVE-018 /btw; external availability not investigated).
- 1 BLOCKED_NO_SOURCE_DATA row (LIVE-016).
- Executed PASS in this audit: 0.
