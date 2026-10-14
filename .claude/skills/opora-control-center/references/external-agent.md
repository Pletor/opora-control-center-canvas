# Podklady pro externího agenta a tickety

Náhled balíčku, neměnný snímek a export zadání pro externího agenta (VS Code / CLI) dělá člověk v panelu **Podklady pro agenta**. Asistent je nevytváří (`/api/desktop-v3/packet/*` není v jeho zápisech); smí je jen číst. Aplikace sama žádný model nespouští.

## Snímek

```bash
python "<SKILL_DIR>/scripts/opora_read.py" snapshot --project <projectId> --workspace <workspace> --id SNAPSHOT_ID
```

Souhrn: `id`, `digest`, `createdAt`, `scope`, `warnings`, `sourceManifest`; `--raw` celý balíček včetně `packet.task.depends_on`. Snímek je neměnný; po změně zadání vzniká nový. Export zapíše soubor do dat plátna (`projects/<id>/packets/external-tasks/<workspace>/<node-id>.md`), ne do repa projektu; odpověď nese absolutní `path` a asistent ho přečte nástrojem `Read` z této cesty.

## Tickety externího agenta

Ticket žije jen ve stavu Desktop v3 (`state.tickets`), v UI se zatím nezobrazuje. Čtení:

```bash
python "<SKILL_DIR>/scripts/opora_read.py" state --project <projectId> --workspace <workspace> --raw
```

Tvar: `{id, title, priority: low|normal|high, status: open|doing|done, nodeId, sessionId, createdBy: human|agent}`, titulek do 400 znaků. Externí agent píše titulek `[external:<status>] tasks/<node-id>.md — …`; `[external:…]` je konvence, ne pole API. `done` od agenta není ověřená oprava ani uzavření; ticket uzavírá člověk.

Asistent tickety nezakládá ani nemění (viz Hranice ve [workflow.md](workflow.md)); co z nich plyne, řekne člověku.
