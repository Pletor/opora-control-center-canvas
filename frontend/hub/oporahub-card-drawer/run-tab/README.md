# Záložka Běh

Nejnovější běh karty z `GET /api/oporahub/executions?nodeId=`: odpočet lease (čas serveru), epocha, snímek zadání (`assignmentDigest`), rozpočet pokusů, oprav a času (`…/execution-budgets`), výsledky kroků a samokontroly z brány review; dole paměť agenta a worktree. Logika: `logic/run-view.ts` (test vedle).
