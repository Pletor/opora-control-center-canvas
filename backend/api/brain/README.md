Router registru Brainu (`backend/brain/`, kontrakt `docs/navrhy/2026-11-03-novy-zaklad.md` §3.4). Je tenký a jen čte, pod `registry_lock`.

| Metoda a cesta | Co dělá |
|---|---|
| `GET /api/brain-registry/artifacts` | artefakty s aktivní verzí a pinem |
| `GET /api/brain-registry/artifacts/{artifact_id}` | artefakt s verzemi (nejnovější první) a vazbami; neznámé ID 404 |
