Router registru Brainu (`backend/brain/`, kontrakt `docs/navrhy/2026-11-03-novy-zaklad.md` §3.4). Je tenký a jen čte, pod `registry_lock`.

| Metoda a cesta | Co dělá |
|---|---|
| `GET /api/brain-registry/artifacts` | artefakty s aktivní verzí a pinem |
| `GET /api/brain-registry/artifacts/{artifact_id}` | artefakt s verzemi (nejnovější první) a vazbami; neznámé ID 404 |
| `GET /api/brain-registry/pins/{plugin}@{sha12}.zip` | zip verze pluginu pro `claude --plugin-dir` (vytvoří ho `Store.export`, když chybí); verze, kterou registr nezná, 404. Přes veřejný tunel jen s přístupovým tokenem (hranice v `backend/app/factory.py`) |
