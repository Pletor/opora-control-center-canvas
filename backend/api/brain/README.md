Router registru Brainu (`backend/brain/`, kontrakt `docs/navrhy/2026-11-03-novy-zaklad.md` §3.4). Je tenký, každé volání drží `registry_lock`. Čtení je volné. Zápis smí člověk (doklad UI) nebo srdce (`X-Opora-Gate-Token` srdce), aktivaci bez evalu (`force`) jen člověk. Logika eval gate je v `backend/brain/evaluate.py`.

| Metoda a cesta | Co dělá |
|---|---|
| `GET /api/brain-registry/artifacts` | artefakty s aktivní verzí a pinem |
| `GET /api/brain-registry/artifacts/{artifact_id}` | artefakt s verzemi (nejnovější první) a vazbami; neznámé ID 404 |
| `POST /api/brain-registry/artifacts/{artifact_id}/candidates` | kandidát: commit souborů pluginu a verze `candidate` s baseline = aktivní; `evals/` 422 |
| `POST /api/brain-registry/versions/{version_id}/evaluate` | běh evalu `running` (202), `claude plugin eval` v pozadí |
| `GET /api/brain-registry/eval-runs/{run_id}` | běh evalu se skóre, baseline, cenou a `passed` |
| `POST /api/brain-registry/versions/{version_id}/activate` | aktivace jen po prošlém evalu (jinak 409 `eval_required`); `{"force": true}` jen člověk, zapíše `forced` |
| `POST /api/brain-registry/artifacts/{artifact_id}/rollback` | návrat na předchozí aktivní verzi bez evalu |

Testy: `test_brain_registry_routes.py` (čtení), `test_brain_eval_gate_routes.py` (gate s podvrženým `claude plugin eval`).
