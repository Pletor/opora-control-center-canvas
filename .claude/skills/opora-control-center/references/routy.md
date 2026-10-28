# Ostatní cesty backendu: co je k čemu a kdy je agent volá

Kdy mě číst: hledáš cestu, která není v [api.md](api.md) ani v [hub-api.md](hub-api.md) (čtecí přehledy Desktop v3,
podklady pro externího agenta, mazání, paměť rolí, mapy, hledání v kódu, asistent v okně). Každá cesta backendu je
popsaná v některé referenci; `scripts/test_skill_docs.py` to hlídá proti tabulce cest aplikace (výjimky jsou jen
cesty §4 `docs/plna-autonomie-agenta.md` a čistě UI).

Všechny cesty kromě aplikačních berou `project` a `workspace` (query u GET, tělo u POST). Zápis mimo skripty:
loopback, stejný `Origin`, `Content-Type: application/json`, `X-Opora-Actor: agent; name=…`. Sloupec **Kdo**:
`kdokoli` = čtení; `agent` = smí agent; `člověk` = jen člověk, nebo agent při plné autonomii ([autonomie.md](autonomie.md));
`člověk (§4)` = jen člověk vždy; `UI` = obsluha okna aplikace, agent nevolá.

## Aplikace a projekt

| Cesta | K čemu, kdy | Kdo |
|---|---|---|
| GET `/api/build-identity` | identita běžícího buildu (verze, commit); ověření, že běží nasazená verze (`opora_read.py status`, [provoz.md](provoz.md)) | kdokoli |
| GET `/api/project-settings` | `project` → `{project, revision, settings, agentAutonomy: {full, since?, by?}}`; zjisti stav plné autonomie | kdokoli |
| POST `/api/project-settings/agent-autonomy` | přesně `{project, full: bool}`; zapne/vypne plnou autonomii agentů; agent 403, neznámý 428 | člověk (§4) |
| POST `/api/sync` | `{project, confirmed: true}` → aktualizace spravovaného mainu projektu z remote (tlačítko v Projektu); agent nevolá, o zastaralém mainu řekne člověku | UI (člověk) |
| POST `/api/project-architecture/journey-runs/{run_id}/progress` | heartbeat přehrávání cesty zákazníka `{segment: {from, to}, ok?}` → 204; volá `tools/journey_run.py` ([journey-run.md](journey-run.md)) | agent (runner) |

## Karta a plátno: čtení

| Cesta | K čemu, kdy | Kdo |
|---|---|---|
| GET `/api/desktop-v3/node-brief` | `nodeId` → karta jako jeden JSON `opora.node-brief/1` (cíl, kroky, kontext, `architecture`, `autonomy {sectorId, grant, policy, full}`); první čtení před prací na kartě (`opora_read.py node-brief`) | kdokoli |
| GET `/api/desktop-v3/work-overview` | co se teď děje: stav karet, agent, časy, čekání na člověka (`work-overview`) | kdokoli |
| GET `/api/desktop-v3/frontier` | `nodeId?` (sektor) → karty k práci, převzaté, blokované, čekající, uzavřené s `missing` (`frontier`) | kdokoli |
| GET `/api/desktop-v3/card-checklist` | `layer` (rodič, `""` = kořen) → kontrolní pás karet vrstvy; co kartám chybí, než je hotová | kdokoli |
| GET `/api/desktop-v3/leases` | aktivní převzetí karet: vlastník, expirace, čas serveru (`leases`); před starým lease | kdokoli |
| GET `/api/desktop-v3/usage-summary` | spotřeba (tokeny, čas, pokusy) po kartách a sektorech (`usage-summary`) | kdokoli |
| GET `/api/desktop-v3/assignment-status` | karty se změněným zadáním od předání nebo výsledku (`assignment-status`); zda pracuješ na aktuálním zadání | kdokoli |
| GET `/api/desktop-v3/assignment-comparison` | `nodeId`, `id`, `source=result` → rozdíl zadání při předání a nyní | kdokoli |
| GET `/api/desktop-v3/source-status` | `sourceRef` karet: present / missing / unavailable (`source-status`) | kdokoli |
| GET `/api/desktop-v3/scenario-history` | poslední běhy scénářů bran (`scenario-history`) | kdokoli |
| GET `/api/desktop-v3/trace` | `id` → co ID je, komu patří, odkud/kam vede; 404 = neexistuje v rozsahu; když máš jen ID z logu nebo zprávy | kdokoli |
| GET `/api/desktop-v3/pipelines` | knihovna předloh pro blok Akce (`library/pipelines.json`) | kdokoli |
| GET `/api/desktop-v3/pipeline-profiles` | šablony profilů pipeline, podlaha, `maxRetries` (`pipeline-profiles`) | kdokoli |
| GET `/api/desktop-v3/agent-results` | `nodeId`, `before?` → neměnná historie výstupů agentů karty (`agent-results`) | kdokoli |
| GET `/api/desktop-v3/agent-workspace-summaries` | vyplněnost prostoru agenta všech karet jedním dotazem; najdi karty bez `handoff` | kdokoli |
| GET `/api/canvas-index` | `q`, `limit` → index karet a vazeb bez obsahu, ETag (`index`, `search`, [rlm.md](rlm.md)) | kdokoli |
| GET `/api/layout-preview` | `layer` → SVG obrys vrstvy (`layout-preview`) | kdokoli |
| GET `/api/node-links` | `node` → odkazy karty na jiné karty (příchozí i odchozí, podle ID); jen pracovní prostor | kdokoli |
| GET `/api/wireframe-context` | `layer` → drátěný model z uložené kresby vrstvy (bloky, prvky, poznámky) jako data | kdokoli |
| GET `/api/drawing-files` | `ids` → obrázky kreseb a podkladů (`drawing-file`, [storyboard.md](storyboard.md)) | kdokoli |
| POST `/api/drawing-file` | `{file: {id, mimeType, dataURL}}` → uloží obrázek kresby / podkladu (PNG skici) | agent i člověk |

## Plátno: lidské zápisy a mazání

| Cesta | K čemu, kdy | Kdo |
|---|---|---|
| POST `/api/canvas-versions/restore` | návrat celého plátna k uložené verzi; neuložené změny se předtím samy uloží jako verze | člověk |
| POST `/api/desktop-v3/autonomy` | `{expectedRevision, sectorId, until, note}` → svěření autonomie sektoru do `until` (prázdné odebere) | člověk |
| POST `/api/desktop-v3/confirm-proposals` | `{sectorId, nodeIds (1–200), expectedRevision}` → hromadné potvrzení návrhů uzavření v sektoru | člověk |
| POST `/api/desktop-v3/rule-review` | `approve` / `reject` návrhu pravidla od agenta | člověk |
| POST `/api/desktop-v3/rule-review-batch` | posouzení víc návrhů pravidel naráz (vše, nebo nic); 409 nese `conflicts` | člověk |
| GET `/api/removal-preview` | `kind`, `target` (u `selection` čárkami 1–500 ID) → co smazání vezme s sebou; čti před `/api/remove` | kdokoli |
| POST `/api/remove` | smaže uzel, vazbu nebo výběr → `recoveryId` (`docs/hromadne-mazani.md`); sektor, brána, > 20 uzlů jen člověk; `kind: "project"` člověk (§4) | agent / člověk |
| POST `/api/remove/restore` | `{recoveryId}` → jednorázový krok zpět po smazání | agent i člověk |

## Podklady pro externího agenta

| Cesta | K čemu, kdy | Kdo |
|---|---|---|
| POST `/api/desktop-v3/packet/preview` | náhled balíčku podkladů karty (nic neukládá) | UI (panel Podklady) |
| POST `/api/desktop-v3/packet/snapshot` | uloží neměnný snímek balíčku → `{id, digest, packet, createdAt}` | UI |
| GET `/api/desktop-v3/packet/snapshots/{snapshot_id}` | jeden snímek (`opora_read.py snapshot`, [external-agent.md](external-agent.md)) | kdokoli |
| POST `/api/desktop-v3/packet/snapshots/{snapshot_id}/external-export` | zapíše zadání pro externího agenta do dat plátna; GET (`nodeId`, `digest`) přečte export | UI / kdokoli čte |

## Schránka zadání: čtení navíc

| Cesta | K čemu, kdy | Kdo |
|---|---|---|
| GET `/api/brief-vault/research-brief` | `fragment` → balíček k výzkumu fragmentu (`research-brief`, [api.md](api.md)) | kdokoli |
| GET `/api/brief-vault/vision` | `scopeNodeId` → představa rozsahu s body trajektorie a trendem shody (`docs/schranka-duel.md`); před `vision-align` | kdokoli |
| GET `/api/brief-vault/mirror` | přesnost Zrcadla po disciplínách a poslední hormony (`docs/zrcadlo.md`); jen přehled | kdokoli |

## Hledání v kódu a v plátně

| Cesta | K čemu, kdy | Kdo |
|---|---|---|
| GET `/api/semantic-search/status` | je sémantický index zdroje k dispozici | kdokoli |
| POST `/api/semantic-search/query` | sémantické hledání v kódu (`find`) | kdokoli |
| GET `/api/code-intelligence/status` | jsou LSP servery pro jazyky prostoru nastavené | kdokoli |
| POST `/api/code-intelligence/query` | přesně `{project, workspace, language, path, operation, line, character}` → LSP (`code`) | kdokoli |
| POST `/api/rlm/rank` | přesně `{project, workspace, query, candidates, top}` → řazení oddílů přes Jev (`rank`, [rlm.md](rlm.md)) | kdokoli |

## Paměť rolí (OpenViking)

| Cesta | K čemu, kdy | Kdo |
|---|---|---|
| GET `/api/memory/status` | `disabled` / `unavailable` / `needs_provisioning` (+ `missingRoles`) / `configured` | kdokoli |
| GET `/api/memory/roles` | knihovna rolí (`library/agent-roles.json`) | kdokoli |
| POST `/api/memory/recall` | vybavení paměti role (`role` nebo `nodeId`, `query`, `maxTokens`) (`recall`) | agent |
| POST `/api/memory/remember` | zápis do sdílené paměti role; `confirmed: true` potvrzuje člověk | člověk |
| POST `/api/memory/lend` | `{fromRole, toRole, query, maxTokens}` → půjčka z paměti jiné role (`origin: lent:<role>`) | agent |
| POST `/api/memory/settings` | `{enabled}` → přepínač paměti pro celou aplikaci | UI (Nastavení) |

## Mapy projektu

| Cesta | K čemu, kdy | Kdo |
|---|---|---|
| POST `/api/graphify/generate` | `project` → vygeneruje graf Graphify ([graphify.md](graphify.md)); spouští člověk tlačítkem | UI |
| GET `/api/graphify/artifact` | `project` → graf (HTML, JSON, počty, otisky); 404 = graf ještě není | kdokoli |
| GET `/api/map-refresh/status` | `project` → stav automatické obnovy map ([map-refresh.md](map-refresh.md)) | kdokoli |
| GET `/api/map-refresh/config` | globální přepínač obnovy map | kdokoli |
| POST `/api/map-refresh/configure` | `{enabled}` → globální přepínač (Nastavení → Obecné) | UI |
| POST `/api/map-refresh/retry` | `project`, `tool?` → zopakuje selhanou obnovu | UI |
| POST `/api/map-refresh/settings` | `{project, tool, automatic}` → obnova po mergi pro projekt | UI |

## Asistent v okně OPORA

Asistenta spouští jen člověk zprávou (`docs/asistent.md`). Agent tyto cesty nevolá; čte jen stav, je-li to potřeba.

| Cesta | K čemu, kdy | Kdo |
|---|---|---|
| GET `/api/assistant/status` | stav procesu asistenta a Jev (`configured`, `provider`, `keys` jako bool) | kdokoli |
| GET `/api/assistant/instructions` | uložené pokyny asistenta (jinak výchozí) | kdokoli |
| POST `/api/assistant/instructions` | `{text \| null}` → uloží / obnoví výchozí pokyny | UI |
| GET `/api/assistant/jev-gate-check` | `project` → pro které poskytovatele je povolená externí kontrola bran | kdokoli |
| POST `/api/assistant/jev-gate-check` | `{project, provider, allowed}` → povolení kontroly bran | člověk |
| GET `/api/assistant/sessions` | `project` → relace asistenta; POST založení viz [api.md](api.md) | kdokoli |
| POST `/api/assistant/sessions/{session_id}/messages` | `{text, context?}` → zpráva člověka relaci (spustí model) | UI |
| POST `/api/assistant/sessions/{session_id}/title` | `{title}` → přejmenování relace | UI |
| POST `/api/assistant/sessions/{session_id}/stop` | zastaví běžící odpověď | UI |
| POST `/api/assistant/sessions/{session_id}/close` | uzavře relaci | UI |
| GET `/api/assistant/sessions/{session_id}/transcript` | přepis relace | kdokoli |
| GET `/api/assistant/sessions/{session_id}/events` | SSE události relace (`after` / `Last-Event-ID`) | UI |
| POST `/api/assistant/approvals/{approval_id}` | `{decision: allow \| deny, note?}` → schválení žádosti asistenta o příkaz | UI (člověk) |
