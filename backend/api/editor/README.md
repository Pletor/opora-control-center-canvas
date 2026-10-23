Rozhraní Editoru: graf plátna, kresby, wireframe kontext, odstraňování (canvas_routes); uložené verze plátna a jejich obnovení (canvas_version_routes); text, odkazy, deník a zadání uzlu (node_routes); stav desktopu, podklady pro agenta a souhrn vyplněnosti karet (desktop_v3_routes); paměť agenta podle role (memory_routes); skills Claude Code a jejich vypnutí (claude_code_routes); řazení oddílů plátna pro asistenta přes Jev, jen loopback (rlm_routes).

`sync_routes` vydává `GET /api/sync-report`: echo a verdikt Oracle pro jeden projekt, jen ke čtení.

`oporahub_process_event_routes` je živý proces (docs/zivy-proces.md): `POST /api/oporahub/process-events` (příjem z kanceláře do outboxu, jen agent) a `GET /api/oporahub/process-health`; události se čtou tokem `opora_event_routes`.
