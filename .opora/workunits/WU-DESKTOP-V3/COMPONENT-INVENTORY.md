# WU-DESKTOP-V3: component inventory (complete)

Base `a0b2c5c`, branch `audit/v3-component-inventory`. Machine data: `component-inventory.json` (125 rows, all preserved).

## Sources (sha256)
| Source | sha256 |
|---|---|
| `E/06 OPORA Desktop v3.dc.html` (684 lines) | `541cb172c681e2e9745ad4da2259a8db10bbab144c46271fb61b83c186428bce` |
| `E/phase2-user-references/USER-BRIEF.md` | `1c3319f796cabdbb69e482060935781dfda079bb9fc79992f7bcd769de3f2b00` |
| `C:/Users/Admin/opora-v3/.opora/goals/desktop-v3-overnight/GOAL.md` | `19723aeaaa75e466703e7640ac13d642d311966d36795df4ef3e9089428c76f7` |

`E` = `C:/Users/Admin/AppData/Local/hermes/handoffs/canvas-orchestration/desktop-v3`. The user supplied all 11 phase-2 images. Phase 2 has its sources and is waiting on phase-1 acceptance; nothing from phase 2 is implemented here.

## Reference binding coverage (machine-checked, exit 0)
| Metric | Count |
|---|---|
| Event tokens (loose scan) / `="{{ binding }}"` occurrences | 143 / 143 |
| onClick / onInput / onKeyDown / onChange | 106 / 19 / 7 / 4 |
| onDragOver / onDragLeave / onDrop / onDragStart | 2 / 2 / 2 / 1 |
| Unique line+event+binding triplets (7 same-line repeats) | 136 |
| Unique binding names | 113 |
| Occurrences mapped to a row / missing / stale refs / duplicate IDs | 143 / 0 / 0 / 0 |
| Rows / rows with binding refs (others: keyboard, props, display, goal) | 125 / 94 |

Two bindings map to more than one row on purpose, because one dynamic control stands for several actions: `386 closeSlash` (V3-ED-020/021/022) and `463 c.run` (V3-LIVE-011/012). The script and its exact command are in `inventory-HANDOFF.md`.

## Status counts (125 rows)
| Status | n |
|---|---|
| IMPLEMENTED_TESTED_SOURCE | 54 |
| PARTIAL | 22 |
| IMPLEMENTED_UNVERIFIED | 16 |
| MISSING | 24 |
| MISSING_REPO_TRANSPORT (new) | 4 |
| BLOCKED_NO_TRANSPORT | 2 |
| BLOCKED_NO_SOURCE_DATA | 1 |
| DEMO_EXCLUDED | 2 |

**A test source is not an executed PASS.** IMPLEMENTED_TESTED_SOURCE means a test file exercises the code. This audit ran no tests, so its **executed PASS count is 0**.

## Corrections in this pass
- **V3-GOAL-003** (general coding dispatch) was `BLOCKED_BY_CONTRACT`; it is now `MISSING_REPO_TRANSPORT`. USER-BRIEF.md supersedes the CONTRACT.md restriction. The repo has three agent paths:
  - a real Hermes documentation-only run (`task_handoff_worker.py:70-122`, writes `result.md` only)
  - calculator-only coding (`coding_worker.py`, `coding_tools.py:10`)
  - `llm_runs.py:229 mode proposal_only`

  None of these meets phase 1. This is a limitation of the repo, not a proven limitation of the provider.
- **V3-GOAL-001 fork, V3-GOAL-002 resume, V3-LIVE-012 CONTINUE/CORRECT** were `BLOCKED_NO_TRANSPORT`; they are now `MISSING_REPO_TRANSPORT`. The installed `claude` 2.1.267 help text lists `--resume`, `--continue`, `--fork-session`, `-p`, `--output-format stream-json`, `--allowedTools` and `--add-dir`. I only read the help text and did not start a model, so these flags are candidates, not verified transport. ESCALATE and COMPLETE are OPORA-local decisions and need no provider transport.
- **V3-LIVE-017 compact, V3-LIVE-018 /btw** stay `BLOCKED_NO_TRANSPORT`, now with a note: I did not investigate whether an external transport exists. A missing repo route does not prove the provider lacks the capability.
- The stale batch label `1/2` is now `complete 2/2`. The legend now marks `BLOCKED_BY_CONTRACT` as retired.

## Phase-1 capability chain (priority order)
1. **Approved snapshot → real scoped coding agent: MISSING_REPO_TRANSPORT** (V3-GOAL-003).
2. **Real artifact + test-result verification: MISSING.** The only existing checks are the calculator oracle and the sha of the documentation `result.md`.
3. **Evidence back to Live Run and the origin node: PARTIAL** (V3-INS-002 tested source; V3-LIVE-005/007 partial; V3-LIVE-012 and V3-GOAL-002 missing).
4. **Reviewed immutable snapshot: source present, not executed here** (`task_handoffs.py:234-392,449`).
5. **Documentation + preview of included sources: IMPLEMENTED_TESTED_SOURCE / PARTIAL** (V3-INS-005/007, V3-PKT-004; V3-TOP-004 and V3-PRJ-018 partial).

The next two TDD tasks are T1 `claude-cli-transport` and T2 `agent-result-evidence`; details are in `inventory-HANDOFF.md`.

## Residual gaps
- 24 MISSING rows. The largest groups are the Projekt tree (expand/collapse, clear search, row keys, per-row add, doc state, fulfilment flow) and cross-mode links (open src/path/run, shelf navigation).
- 22 PARTIAL rows.
- 16 IMPLEMENTED_UNVERIFIED rows have no test source.
