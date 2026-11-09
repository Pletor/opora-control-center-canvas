# Ostatní cesty backendu: co je k čemu a kdy je agent volá

Kdy mě číst: hledáš cestu, která není v [api.md](api.md) ani v [hub-api.md](hub-api.md) (čtecí přehledy Desktop v3,
podklady pro externího agenta, mazání, paměť rolí, mapy, hledání v kódu). Každá cesta backendu je
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

## Rozhodovací model Jev

Nastavení aplikace, jen loopback (`docs/brain-heart-channel.md` §5). Klíč (`POST /api/brain/jev/key`) ukládá jen člověk
a agent ho nikdy nečte ani nezapisuje.

| Cesta | K čemu, kdy | Kdo |
|---|---|---|
| GET `/api/brain/jev` | `configured`, `provider`, `keys` (jen bool) zvoleného poskytovatele Jev | kdokoli |
| GET `/api/brain/jev/gate-check` | `project` → pro které poskytovatele je povolená externí kontrola bran | kdokoli |
| POST `/api/brain/jev/gate-check` | `{project, provider, allowed}` → povolení kontroly bran | člověk |

## Karta na dvě volání (složené akce)

| Cesta | K čemu, kdy | Kdo |
|---|---|---|
| POST `/api/oporahub/executions/start` | `{project, workspace, nodeId, ttlSeconds?}` → kontext v2, hlavy z čerstvého stavu, claim a zadání jedním voláním: `{executionId, token, epoch, expiresAt, acceptedRevision, contextVersion, resumed, assignment, steps: [{id, title, dod, status}], next}`; týž aktér s živým převzetím dostane stávající běh (`resumed: true`); cizí převzetí 409 `card_leased`, bez přijatého grafu 409 `graph_acceptance_required` (`hint`); jen `opora_hub.py start --node N` (token) | agent i člověk |
| POST `/api/oporahub/executions/{identifier}/deliver` | hlavička `X-Opora-Execution-Token`; `{project, workspace, summary, steps?: [{stepId, status, notes?}], commit?, checks?: [{name, status: green\|red, output?}], decisions?, close?}` → kroky (bez `notes` z commitů karty s `Opora-Node`, jinak `summary`), výsledek se `selfChecks`, lokální sloučení (bez GitHubu, výchozí commit = HEAD), běhy kontrol a při plné autonomii uzavření stejnou bránou: `{delivered, merged, checks, closed, missing, leaseRenewed, next}`; červená kontrola uzavření zastaví; vypršelé převzetí přijme, když kartu nikdo nepřevzal (`lease_renewed_on_deliver`), jinak 409 `execution_superseded`; cizí změna kontextu 409 `execution_context_changed` („spusť start znovu“); vlastní `canvas-plan` kontext přepne (`rePinned` v odpovědi dávky); jen `opora_hub.py deliver` | agent i člověk |

## Rešerše: ověřené podklady a návaznost zadání

Všechna volání nesou `project` a `workspace`; `main` se překládá na aktivní pracovní prostor. Čtení dovoluje
člověk nebo token Srdce/dělníka ve stejném prostoru, zápisy člověk nebo token Srdce. Samotné vyřešení karty,
vazba ani přezkum rozhodnutí nejsou přijetím zadání v OporaHubu.

| Cesta | K čemu, kdy | Kdo |
|---|---|---|
| GET `/api/research` | hlavičky karet a směrované významové vazby; `archived` zahrne archiv | člověk, Srdce, dělník |
| POST `/api/research` | `{project, workspace, key, operations}`: verzované karty, vazby a archivace; `expectedRevision` hlídá souběh, opakovaný `key` se stejným obsahem vrátí původní výsledek | člověk, Srdce |
| GET `/api/research/cards/{id}` | úplná karta, zdroje, historie a vazby; `revision` připne historickou revizi | člověk, Srdce, dělník |
| GET `/api/research/edges/{id}` | význam a historie konkrétní vazby, volitelná `revision` | člověk, Srdce, dělník |
| GET `/api/research/topics` | hierarchie témat; `archived` zahrne archivované karty | člověk, Srdce, dělník |
| GET `/api/research/cards/{id}/parts` | úplné podklady po označených částech: `revision`, `offset`, `size`, `snapshot`; obsah se tiše nezkracuje | člověk, Srdce, dělník |
| GET `/api/research/events` | synchronizační události prostoru po kurzoru `after`, dávka `limit` | člověk, Srdce, dělník |
| GET `/api/research/decision-reviews` | historie neměnných lidských přezkumů karty `decisionId` | člověk, Srdce, dělník |
| POST `/api/research/decision-reviews` | `{project, workspace, review}`; přezkum připne `decisionId`, kladnou celočíselnou `decisionRevision`, `problemId`, `evidence: [{id, revision}]`, `rationale`, `assumptions`, `constraints` | pouze člověk |
| GET `/api/research/decision-reviews/{id}` | úplný přezkum s původním problémem, rozhodnutím a podklady, zachovaný i po změně zadání | člověk, Srdce, dělník |
| POST `/api/research/decision-reviews/{id}/tasks` | `{project, workspace, tasks}` vytvoří nativní návrh OporaHubu; úkol: `ref` ([a-z0-9-], nejvýše 80 znaků), `title`, `goal`, `acceptance`, `dependsOn`, volitelně `parentId` či existující `nodeId`. Existující úkoly mají prázdné `dependsOn`; změny pořadí patří do návrhu grafu. Nové a existující úkoly jsou oddělené návrhy. Přijetí zůstává v OporaHubu | člověk, Srdce |
| GET `/api/research/decision-reviews/{id}/tasks` | receipt s `proposalId`, skutečnými `nodeIds`, stavem `accepted` a `acceptedRevision` odvozeným z nativní historie | člověk, Srdce, dělník |
| POST `/api/research/decision-reviews/{id}/reconcile` | `{project, workspace}` po skutečném přijetí návrhu doplní zpětné vazby do Rešerše; bezpečné opakování, před přijetím 409 | člověk, Srdce |
| POST `/api/research/tickets/branch` | `{project, workspace, ticketId, feedbackId}` otevře větev z existující zpětné vazby Kanceláře; identitu relace, úkolu a jeho verze převezme server | člověk, Srdce |
| POST `/api/research/tickets/answer` | `{project, workspace, ticketId, feedbackId, cardId, revision, text}` připne rešeršní odpověď a přes existující ticket ji doručí původní relaci; vyžaduje vazbu `resolves`, opakovaná stejná odpověď je replay | člověk, Srdce |

## Pletor: rozhovor, přehled a nastavení

Celý prefix `/api/pletor` je omezen na tento počítač (loopback). Následující rozhovor, přehled, nastavení
modelů a hlasu vyžadují člověka v UI; agent si těmito cestami nemění účet ani oprávnění. Parametry
`project` a `workspace` jsou v query u čtení a v těle zprávy. Každá sekce přehledu může vrátit vlastní chybu.

| Cesta | K čemu, kdy | Kdo |
|---|---|---|
| POST `/api/pletor/messages` | `{project, workspace, text, voice?}` → odpověď a provedené akce | člověk |
| GET `/api/pletor/messages` | `project`, `workspace`, `limit` 1–500, `q` → filtrovaná historie a celkový počet | člověk |
| POST `/api/pletor/messages/stream` | stejné tělo jako zpráva; NDJSON události `delta` a konečné `done` s odpovědí a akcemi | člověk |
| GET `/api/pletor/state` | `project`, `workspace` → rozhovor, Srdce, eskalace a zvolený mozek | člověk |
| POST `/api/pletor/brain` | `{brain: claude/codex/ollama, model?, effort?}` přepne mozek Pletora; výsledek obsahuje `ok`, `reply`, `brain` | člověk |
| GET `/api/pletor/heart` | `project`, `workspace` → stav Srdce, fronta, dávky, brána a mozek | člověk |
| GET `/api/pletor/context` | `project`, `workspace` → kontext a přehled sekcí s počty znaků, limity a příznaky zkrácení | člověk |
| GET `/api/pletor/monitoring` | `project` → hostitelé, události a příznak zapnutí sledování | člověk |
| GET/PUT `/api/pletor/heart/model` | čtení modelu a poradce Srdce; PUT `{model, advisor, effort?}` vytvoří novou verzi jeho toku | člověk |
| GET `/api/pletor/voices` | hlasy, dostupnost a případná kvóta; `warm` přednačte zvolený hlas | člověk |
| POST `/api/pletor/tts` | `{text, voice?}` → zvuk podle enginu, případně stream; nedostupný hlas/engine vrací chybu | člověk |
| GET `/api/pletor/llm` | dostupnost a nastavení lokálních Claude Code, Codex, Ollama a přepínačů účtů | člověk |
| PUT `/api/pletor/llm/claude` | `{model, effort?}` zapíše nastavení Claude Code se zálohou | člověk |
| PUT `/api/pletor/llm/codex` | `{model, reasoning?}` zapíše nastavení Codexu se zálohou | člověk |
| POST/DELETE `/api/pletor/llm/{tool}/login` | `tool` je `cswap` nebo `codex`; POST zahájí přihlášení a vrátí URL, DELETE zruší probíhající přihlášení | člověk |
| POST `/api/pletor/llm/{tool}/login/code` | `{code?}` dokončí přihlášení nebo uloží již přihlášený účet | člověk |
| POST `/api/pletor/llm/{tool}/switch` | `{slot}` přepne uložený účet příslušného nástroje | člověk |

### Žádosti a odpovědi Srdce

Všude query `project`. Identita původce je člověk v UI, hlavička `X-Opora-Actor: agent; name=…` nebo token
brány `X-Opora-Gate-Token`; token musí patřit projektu. Čtení žádostí níže nevyžaduje zvláštní identitu původce,
ale stále platí přístupová hranice aplikace a loopback. Odpověď na otázku se nepovažuje za přijetí plánu.

| Cesta | K čemu, kdy | Kdo |
|---|---|---|
| POST `/api/pletor/requests` | `{text, idempotencyKey}` založí žádost; stejný klíč a text vrátí tutéž žádost, změněný text 409 | člověk nebo agent |
| GET `/api/pletor/requests` | `open=1` omezí výpis na otevřené žádosti; vrací i počet otevřených | čtení v aplikaci |
| GET `/api/pletor/requests/{request_id}` | detail žádosti a potvrzených kroků | čtení v aplikaci |
| POST `/api/pletor/requests/{request_id}/steps` | `{k: plan/ticket/attempt/commit, evidence}` nebo `{k, failed:true, why}`; služba ověří důkaz kroku | pouze agent/služba |
| GET `/api/pletor/questions` | seznam otázek a právě otevřená otázka pro panel | člověk |
| POST `/api/pletor/questions/{question_id}/answer` | `{text, refs?, unknown?, reason?}`; stejná odpověď je replay, nová vyvolá výklad Pletora; `unknown` vyžaduje důvod | pouze agent/Srdce |

## Linie: větve a práce Kanceláře

Přehled větví, náhledy a jednoduchý záznam nasazení ovládá jen člověk v UI. Následující cesty používají
repozitář služby; `project` přidává přijaté práce konkrétního projektu. Nepřijímají libovolný kořen repozitáře.

| Cesta | K čemu, kdy | Kdo |
|---|---|---|
| GET `/api/pletor/linie/` | `project?` → main, develop, server, nasazená revize, větve, náhledy a vynucení pravidel | člověk |
| GET `/api/pletor/linie/graph` | `project?` → větve a jejich návaznosti, aktivní práce, server a nasazená revize | člověk |
| GET `/api/pletor/linie/diff` | `branch`, `target` → commity, statistika a změněné soubory | člověk |
| POST `/api/pletor/linie/previews` | `{branch, project}` spustí sestavení náhledu nad kopií dat projektu | člověk |
| DELETE `/api/pletor/linie/previews/{slug}` | zastaví daný náhled | člověk |
| GET `/api/pletor/linie/previews/{slug}/log` | výstup sestavení a serveru náhledu | člověk |
| POST `/api/pletor/linie/deployed` | `{sha}` uloží revizi označenou jako nasazenou; samo aplikaci nenasazuje | člověk |

### Editor a životní cyklus práce

Všude query `project`; přehled a založení práce navíc `workspace` (výchozí `main`). „Člověk/agent“ vyžaduje
identitu původce popsanou výše; token pracovníka musí patřit prostoru ticketu, Srdce pracuje v projektu.
Přijetí a povolení sloučení zůstávají lidské kroky. Služba odmítne přechod nedovolený aktuálním stavem 409
`action_not_allowed`; shodný idempotentní klíč či `op` neprovádí operaci znovu.

| Cesta | K čemu, kdy | Kdo |
|---|---|---|
| GET `/api/pletor/linie/board` | `workspace`, `group=branch/plan`, `snapshot?` → osy, práce a důkazy; snapshot dovoluje stejné údaje přeskupit | člověk |
| GET `/api/pletor/linie/board.txt` | textový snímek; `workspace`, `mine=1` jen práce volajícího agenta, `all=1` i uzavřené řádky | člověk/agent; `mine` jen agent |
| POST `/api/pletor/linie/rows` | `{name, type:items/work/experiment/fix, base?, target?}` založí řádek | člověk |
| PATCH/DELETE `/api/pletor/linie/rows/{row_id}` | PATCH mění `name`, `branch`, `target`, `collapsed`; DELETE odmítne řádek používaný prací | člověk |
| POST `/api/pletor/linie/work` | `{title, branch, essence, build, doneCriteria, rowId?, baseBranch?, target?, requestId?, idempotencyKey?}` založí ticket práce a vazbu na řádek | člověk |
| POST `/api/pletor/linie/work/{ticket_id}/attach` | `{rowId, branch, baseBranch?, target?, title?, requestId?}` připojí existující ticket do Linie | člověk |
| GET `/api/pletor/linie/work/{ticket_id}` | ticket, stav práce, povolené akce, osy a důkazy | člověk/agent |
| GET `/api/pletor/linie/commit/{sha}` | `workspace?` → detail commitu s plánem, kartou, Kanceláří, PR a náhledem | čtení v aplikaci |
| GET `/api/pletor/linie/trace/{mark}` | `workspace?` → cesta práce podle značky OP-XXXXXX; neznámá značka 404 | čtení v aplikaci |
| GET `/api/pletor/linie/journal` | `workspace?`, `after`, `limit` → deník událostí Linie a `lastId` | čtení v aplikaci |
| POST `/api/pletor/linie/work/{ticket_id}/run` | `{sessionId, agent?, transcriptPath?, worktree?}` eviduje relaci LLM; stejné ID aktualizuje heartbeat | člověk/agent |
| POST `/api/pletor/linie/work/{ticket_id}/report` | `{sha, checks:[{name,status:green/red/pending}], worktree?}` hlásí hlavu a kontroly, publikuje pokus a naváže krok žádosti | člověk/agent |
| POST `/api/pletor/linie/work/{ticket_id}/attempt` | `{branch, baseRef?, baseSha?, repo?, agent?, requestId?, idempotencyKey?}` eviduje pokus práce; větev vytváří agent | člověk/agent |
| POST `/api/pletor/linie/work/{ticket_id}/preview` | spustí náhled větve ticketu a připne jeho revizi | člověk |
| POST `/api/pletor/linie/work/{ticket_id}/tried` | `?project=<id>`, JSON `{}`; po skutečném otevření běžícího náhledu člověkem vrátí aktualizovaný ticket s `work.tried={sha,at}` a zapíše `linie.preview.tried`. SHA bere z náhledu, nikoli ze vstupu; bez běžícího náhledu 409 `preview_not_running`. Nepřijímá ani neslučuje práci; agent nesmí tento lidský doklad nahrazovat vlastním tvrzením. | pouze skutečný člověk v UI (`require_human`, i při plné autonomii) |
| POST/DELETE `/api/pletor/linie/work/{ticket_id}/accept` | POST `{sha, note?}` přijme konkrétní aktuální hlavu; DELETE toto přijetí odvolá | člověk |
| POST `/api/pletor/linie/work/{ticket_id}/allow-merge` | `{target?}` povolí sloučení přijaté hlavy do konkrétního cíle a jeho aktuální revize | člověk |
| POST `/api/pletor/linie/work/{ticket_id}/accept-merge` | `{sha, op?, note?}` provede přijetí, povolení a sloučení, zastaví se na první zavřené bráně | člověk |
| POST `/api/pletor/linie/work/{ticket_id}/merge` | volitelné `{op}` provede pouze již povolené sloučení; stejné `op` je replay | člověk/agent |
| POST `/api/pletor/linie/work/{ticket_id}/revert` | `{sha, expectedHead, op?}` vytvoří revert na větvi úkolu s kontrolou očekávané hlavy | člověk/agent |
| POST `/api/pletor/linie/work/{ticket_id}/rebase-note` | `{from, to}` uloží doklad rebase; samo Git nepřepisuje | člověk/agent |
| POST `/api/pletor/linie/work/{ticket_id}/abandon` | `{sha, why}` eviduje opuštěnou práci; HEAD ani Git nemění | člověk/agent |
| POST `/api/pletor/linie/work/{ticket_id}/block` | `{reason}` označí překážku práce | člověk/agent |
| POST `/api/pletor/linie/work/{ticket_id}/defer` | odloží práci, bez změny Gitu | člověk/agent |
| POST `/api/pletor/linie/work/{ticket_id}/unblock` | odstraní označení překážky | člověk/agent |
| POST `/api/pletor/linie/work/{ticket_id}/resume` | zruší odložení i překážku a obnoví práci | člověk/agent |
| POST `/api/pletor/linie/work/{ticket_id}/forget` | odstraní jen blokovaný ticket, jehož kód už je v cíli nebo nemá vlastní commity; zachová událost v deníku, živý kód vrací 409 | člověk/agent |
| POST `/api/pletor/linie/deploy` | `{env, sha, repo?}` zaznamená nasazení existující revize, samo nenasazuje; `repo` smí být jen repozitář služby, oprávnění cíle určuje `[linie.deploy]` v `opora.local.toml` | povolený člověk/agent |

## Dílna funkcí a skillů

Cesty `/api/pletor/workshop` jsou jen pro člověka v lokálním UI. Názvy, cesty a obsah ověřuje úložiště:
chybný vstup 422, neznámý záznam 404, již existující název 409. Generování používá aktuální mozek Pletora.

| Cesta | K čemu, kdy | Kdo |
|---|---|---|
| GET/POST `/api/pletor/workshop/tools` | GET seznam funkcí; POST `{name}` vytvoří šablonu s případem | člověk |
| GET/PUT `/api/pletor/workshop/tools/{name}` | GET zdrojový kód a případy; PUT `{code, cases}` je uloží jako text | člověk |
| POST `/api/pletor/workshop/tools/generate` | `{name, intent}` vygeneruje novou funkci a případy, uloží je a změří; existující název nepřepíše | člověk |
| POST `/api/pletor/workshop/tools/{name}/measure` | změří uložené případy; vrací počty, chyby, dobu a determinismus | člověk |
| GET/POST `/api/pletor/workshop/skills` | GET seznam skillů a souborů; POST `{name}` vytvoří skill | člověk |
| GET/PUT `/api/pletor/workshop/skills/{name}/file` | GET `path=SKILL.md` vrátí soubor; PUT `{path, content}` uloží jeho obsah v mezích úložiště | člověk |
## Rešerše a navazující plánování

Připravené posouzení není lidské rozhodnutí ani přijetí plánu. Agent ukládá neměnný návrh s přesnými revizemi otázky, rozhodnutí a zdrojů; člověk jej čte v panelu rozhodnutí Rešerše. Změna libovolného podkladu blokuje potvrzení. Záznam lidského posouzení a stav návrhu se potvrzují v jedné SQL transakci; staré návrhy i původní přímé lidské posouzení zůstávají čitelné.

| Cesta | K čemu, kdy | Kdo |
|---|---|---|
| POST `/api/research/review-proposals` | `{project, workspace, review, requestId}` připraví přesný návrh; stejný klíč vrací původní záznam, jiný obsah pod stejným klíčem 409 | člověk nebo ověřené Srdce stejného rozsahu |
| GET `/api/research/review-proposals` | `project, workspace, decisionId` → návrhy a historie pro dané rozhodnutí | oprávněný čtenář rozsahu |
| GET `/api/research/review-proposals/{identifier}` | `project, workspace` → celý neměnný podklad a stav lidského rozhodnutí | oprávněný čtenář rozsahu |
| POST `/api/research/review-proposals/{identifier}/{action}` | `{project, workspace, digest}`; `accept` uloží nativní lidské posouzení, `reject` zachová zamítnutou historii; přijetí plánu je samostatné | pouze ověřený člověk |

Soukromé připojení pohledu vyžaduje ověřenou lidskou relaci prohlížeče. Připojovací tajemství zůstává v dané záložce; samotný požadavek Srdce neznamená vykreslení. Stav `applied` potvrzuje až přesná revize a pohled skutečně převzaté UI.

| Cesta | K čemu, kdy | Kdo |
|---|---|---|
| GET `/api/canvas-view-attachments/sessions` | `project, workspace` → dostupné relace Srdce ve zvoleném rozsahu, bez tokenů | ověřený lidský prohlížeč |
| POST `/api/canvas-view-attachments/{action}` | `attach`, `poll`, `ack`, `pending`, `detach`; vždy `project, workspace, sessionId`, po připojení také `attachmentId, secret`, při `ack` přesné `revision, view, renderEpoch`; expirace a nahrazení ruší staré potvrzení | ověřený lidský prohlížeč |
| GET `/api/site-admin/proposals/{proposal_id}/attachments/{index}` | `project` → neměnné bajty přílohy návrhu s ověřeným SHA256; bezpečné stažení, nikoli zveřejnění ani přijetí | ověřený člověk nebo Srdce s tokenem stejného projektu |

| Cesta | K čemu, kdy | Kdo |
|---|---|---|
| GET `/api/research/continuations` | `project, workspace` → trvalé stavy navazujícího plánování; dokončení dokládá uložený nativní návrh, nikoli pouze úspěšný běh LLM | oprávněný člověk/agent ve stejném rozsahu |
| GET `/api/research/originals/{identifier}` | `project, workspace, revision?` → původní rešerše, její revize, historie a odkazy na mapu; původní stav se nemění | oprávněný člověk/agent ve stejném rozsahu |
| POST `/api/research/originals/{identifier}/materialize` | `{project, workspace, revision, detailsRevision}` → stabilní karta původní rešerše; opakování je idempotentní, starší revize vrací 409, ruční vazby zůstávají | oprávněný člověk/agent ve stejném rozsahu |
| GET `/api/brain/canvas/capabilities` | `project, workspace` → konečný seznam schopností Srdce v přesném rozsahu včetně nepodporovaných operací | Srdce s tokenem daného rozsahu |
| GET `/api/brain/canvas/capabilities/{operation_id}` | `project, workspace` → typovaný nativní kontrakt zvolené operace | Srdce s tokenem daného rozsahu |
| POST `/api/brain/canvas/invoke` | `{project, workspace, capability, input, requestId?}` → pouze implementované adaptéry; stabilní `requestId` chrání opakování změny, nepodporovaná operace vrací 409; lidské rozhodnutí se jen připraví, relace vrací `applied:false` | Srdce s tokenem přesného rozsahu |

| POST `/api/oporahub/graph-proposals/{identifier}/revise` | `project, workspace, expectedAcceptedHead, expectedGraphDigest, subject, plan, observeResearchSources: true, operationId` -> immutable superseding V3 proposal; retained server-owned identities, explicitly refreshed source pins, scoped replay; no acceptance | Verified scoped Heart or native authorized proposal actor; superseded drafts cannot be accepted or revised again under a new operation |


### Library review

| GET | `/api/oporahub/baseline-preparations/{identifier}` | Scoped immutable baseline preparation receipt with exact pinned documents/context; read only. Human acceptance remains `/api/oporahub/baselines` with native CAS. |

| Method | Route | Contract |
| --- | --- | --- |
| GET | `/api/library/reviews` | Scoped project/workspace native reviews; human session or scoped token. |
| GET | `/api/library/reviews/{identifier}` | Immutable input and preimage, current review decision and native result. |
| POST | `/api/library/reviews/{identifier}/{action}` | Human-only accept/reject, scoped body project/workspace; native CAS and atomic registry write. |

| GET | `/api/flow/review` | Scoped native Flow review: `project`, `workspace`, `operation`, `identifier`; exact immutable version/run plus current review digest. Authenticated Heart may read its authorized scope; this endpoint never approves or activates. |

| GET | `/api/desktop-reviews/{identifier}` | Human or scoped Heart reads immutable preparation by exact ID; project/workspace required, returns pinned parameters and current freshness. |
| POST | `/api/desktop-reviews/{identifier}/apply` | Human-only apply of immutable preparation, project/workspace/digest required. Graph and state pins checked under native locks; stale or edited preparation rejected. Native state remains applied truth. |

| GET | `/api/working-reviews/{operation}/{identifier}` | Exact scoped immutable native working graph/removal/recovery preparation and separate application readback; project/workspace required. No acceptance. |
| POST | `/api/working-reviews/{operation}/{identifier}/apply` | Authenticated human applies the exact scoped native preparation under its pinned preconditions; payload project/workspace. Native graph/removal/recovery validation and authority remain unchanged. |


| Route | Contract | Authority |
| --- | --- | --- |
| GET `/api/brief-vault/reviews/{identifier}` | `project,workspace` -> immutable native vault intent, exact preimage and separate decision receipt | Authenticated human or scoped agent; no decision |
| POST `/api/brief-vault/reviews/{identifier}/{action}` | `{project,workspace,digest}`, action accept/reject -> native operation or rejection with durable replay; stale preimage conflicts | Authenticated human only; full agent authority cannot impersonate a human |

Vault capability `brief_vault_routes.brief_vault_write` exposes the finite27-operation matrix in `backend/editor/brief_vault/operation_review_contracts.py`; tests `test_operation_review_workflows.py`, `test_operation_review_placement.py`, `test_operation_review_duel.py`, `test_operation_reviews.py` and `test_canvas_capability_brief_operations.py` distinguish native agent operations from actual human review.
