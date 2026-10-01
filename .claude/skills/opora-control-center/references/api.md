# API — přesný scope, čtení a bezpečný zápis

Toto je příručka pro autorizovanou práci přes HTTP, ne univerzální admin API.
Pomocný `scripts/opora_read.py` čte přes GET a POST posílá jen na pevný seznam čtecích dotazů
(`POST_ROUTES`: LSP, sémantika, paměť, řazení RLM); nic nemění a nic nespouští.

## Spuštění skriptu

```bash
python "<SKILL_DIR>/scripts/opora_read.py" --help
python "<SKILL_DIR>/scripts/opora_read.py" --base-url http://127.0.0.1:8740 workspaces --project ID
python "<SKILL_DIR>/scripts/opora_read.py" --base-url http://127.0.0.1:8740 node-spec --project ID --workspace ID --node ID --raw
python "<SKILL_DIR>/scripts/opora_read.py" --base-url http://127.0.0.1:8740 sessions --project ID --workspace ID --node ID
python "<SKILL_DIR>/scripts/opora_read.py" --base-url http://127.0.0.1:8740 snapshot --project ID --workspace ID --id SNAPSHOT_ID
python "<SKILL_DIR>/scripts/opora_read.py" --base-url http://127.0.0.1:8740 node-brief --project ID --workspace ID --node ID
python "<SKILL_DIR>/scripts/opora_read.py" --base-url http://127.0.0.1:8740 frontier --project ID --workspace ID --node SEKTOR_ID
```

`node-brief` vrací balíček karty (`/api/desktop-v3/node-brief`). `frontier` je mapa wayfinderu
nad sektorem: karty rozdělené na `frontier`, `claimed`, `blocked`, `closed` (viz workflow.md).

Bez `--base-url` i `--api-base` vezme skript adresu z `OPORA_BASE_URL` (asistent ji dostane
od své instance). Musí to být loopback jako u `--base-url`.

### Hledání (jen čtení)

```bash
python "<SKILL_DIR>/scripts/opora_read.py" search --project ID --workspace ID --query "platby" [--layer ID]
python "<SKILL_DIR>/scripts/opora_read.py" index --project ID --workspace ID [--layer ID]
python "<SKILL_DIR>/scripts/opora_read.py" rank --project ID --workspace ID --query "kde se řeší platby" [--layer ID] [--top 10]
python "<SKILL_DIR>/scripts/opora_read.py" code --project ID --workspace ID --path src/app.ts --operation references --line 10 --character 4
python "<SKILL_DIR>/scripts/opora_read.py" find --project ID --workspace ID --query "uložení stavu" [--path .] [--limit 10]
python "<SKILL_DIR>/scripts/opora_read.py" recall --project ID --workspace ID --query "rozhodnutí" (--role R | --node N) [--max-tokens N]
```

| Příkaz | Co dělá |
|---|---|
| `search` | GET view + `desktop-v3/state`; karty, kde je každé slovo dotazu v názvu, účelu, blocích, kritériích nebo krocích. Bez velikosti písmen a diakritiky, nejvýš 20 `{id, name, parentId, kde}`. Spec se neprohledává (`note`) |
| `index` | oddíly plátna bez obsahu `{id, name, parentId, kind, chars}`; `chars` = délka účelu, bloků, kritérií a kroků |
| `rank` | kandidáti z indexu (nejvýš 255, text ≤ 300 znaků) → `POST /api/rlm/rank`; `{status: ok, ranked: [{id, p, name}]}` nebo `unavailable` (Jev bez klíče či v poruše). Postup: [rlm.md](rlm.md) |
| `code` | `POST /api/code-intelligence/query` `{project, workspace, language, path, operation, line, character}`; `operation` = `definition\|references\|hover\|documentSymbols`, jazyk z přípony (`typescript` / `python`), řádek a znak od nuly. Textový dotaz LSP nemá |
| `find` | `POST /api/semantic-search/query` `{project, workspace, path, query, limit}`; `path` je relativní podstrom, `limit` 1–20 |
| `recall` | `POST /api/memory/recall` `{role, project, workspace, nodeId, query, maxTokens}`; bez role a karty vrátí backend `skipped` |

Pořadí hledání: plátno `search` (nebo `index` → `rank`) → `find` / `code` → graphify → Archify →
`recall` → web. POST na jinou cestu skript odmítne dřív, než cokoli odešle.

Výstup je JSON na stdout. Návratový kód 0 = požadované čtení uspělo;
1 = chybný vstup / nedostupnost. Kód 0 neznamená úspěšné splnění uživatelského
úkolu. Skript odmítá redirecty a proxy a omezuje velikost odpovědi.
`--base-url` pustí jen loopback; vzdálená adresa jde výhradně přes `--api-base https://HOST`
a jen s tokenem v `OPORA_ACCESS_TOKEN`. Skript čte jen tuhle proměnnou a `OPORA_BASE_URL`.

Po readbacku snapshotu porovnej očekávané ID, digest a node s uloženým zadáním;
skript sám nezná očekávaný digest. `--raw` je plný obsah, nikoli redaktor tajemství.

## Čtení — doložené routy

| GET | Parametry / použití |
|---|---|
| `/api/health` | identita Opora Canvas a dostupnost |
| `/api/build-identity` | identita backendu **při startu**, ne nového statického buildu |
| `/api/bootstrap` | `draft`, `projects`, `jobs`; seznam projektů je **jen zde** — žádné `/api/projects` neexistuje |
| `/api/project-settings` | project; zadání a další nastavení projektu (bez provider/model/limitu) |
| `/api/project-workspaces` | project |
| `/api/view` | project, workspace; `graph`, `digest`, `readOnly` |
| `/api/node-text` | project, workspace, node |
| `/api/node-spec` | project, workspace, node |
| `/api/node-spec/history` | project, workspace, node |
| `/api/node-journal` | project, workspace, node, day |
| `/api/node-links` | project, workspace, node |
| `/api/drawing` | project, workspace, layer |
| `/api/wireframe-context` | project, workspace, layer |
| `/api/desktop-v3/state` | project, workspace; revision, state, readOnly |
| `/api/desktop-v3/block` | project, workspace, nodeId, blockId; adresný jeden blok s dětmi/rodičem, 404 = neexistuje |
| `/api/desktop-v3/agent-workspace` | project, workspace, nodeId; `revision`, `workspace` {frame, log, failures, fixes, handoff, updatedAt, by}, `readOnly`; prázdný prostor = revision 0, 404 = karta neexistuje |
| `/api/desktop-v3/agent-workspace-summaries` | project, workspace; `readOnly`, `items` {nodeId: {filled, by, updatedAt}} pro každý uzel grafu kromě komentářů; jedním dotazem |
| `/api/desktop-v3/node-brief` | project, workspace, nodeId; karta jako jeden JSON pro model (`opora.node-brief/1`): cíl, DoD, hranice, kontext, rodiče, děti, paměť role, `outputContract`. Je to popis stavu, ne příkaz. Kontrakt: `docs/karta-pro-agenty.md` |
| `/api/desktop-v3/trace` | project, workspace, id; co ID je, komu patří a odkud/kam vede; 404 = neexistuje |
| `/api/desktop-v3/tags` | project, workspace; index štítků ze stavu |
| `/api/desktop-v3/pipelines` | bez parametrů; knihovna předloh pro blok Akce (`library/pipelines.json`) |
| `/api/desktop-v3/agent-messages` | project, workspace, nodeId, `direction: incoming\|outgoing`, volitelně `before`; stránka 30, `hasMore`, `nextBefore` (karta-pro-agenty.md, Adresovaná komunikace) |
| `/api/node-materials/file` | project, nodeId, file; soubor nahraného podkladu, 404 = není uložen |
| `/api/memory/status`, `/api/memory/roles` | stav paměti rolí a knihovna rolí; viz `docs/pamet-agentu.md` |
| `/api/processes` | project, volitelně state, nodeId; procesy s povolenými přechody |
| `/api/processes/{id}` | project; proces, posledních 20 odpovědí, povolené přechody |
| `/api/removal-preview` | project, workspace, kind, target; náhled odstranění s `digest` (pro projekt: `workspace=main`, `kind=project`, `target=ID projektu`) |
| `/api/desktop-v3/packet/snapshots/{id}` | project, workspace |
| `/api/desktop-v3/packet/snapshots/{id}/external-export` | project, workspace, nodeId, digest; readback exportu |
| `/api/node-sessions` | project, workspace, volitelně nodeId; limit 100, `truncated` |
| `/api/agents/sources`, `/api/agents/runs`, `/api/agents/runs/{source}/{run}`, `/api/agents/unbound`, `/api/agents/bindings`, `/api/agents/activity` | telemetrie agentů, pouze čtení |
| `/api/map-refresh/status` | project; viz map-refresh.md |
| `/api/map-refresh/config` | `{enabled}` globální automatiky map; viz map-refresh.md |
| `/api/archify/artifact` | project; stabilní sada z `archify-out/` hlavního projektu |
| `/api/graphify/artifact` | project; stabilní sada z `graphify-out/` hlavního projektu |
| `/api/agent-hooks` | project, workspace, nodeId; `bindings`, `readOnly`, `taskRevision` (Hook control, nic nespouští) |
| `/api/agent-hooks/events` | bindingId; posledních 50 událostí, `truncated`, bez obsahů nástrojů |
| `/api/agent-hooks/vscode` | bindingId; stav instalace hooku do `.claude/settings.local.json` workspace (bez zápisu) |
| `/api/code-intelligence/status` | project, workspace; LSP providery (`configured` ≠ běží), `semantic` stav z reálné služby, `preference` |
| `/api/semantic-search/status` | project, workspace; lokální ONNX model `configured`/`unavailable`, žádný download |

## Vzdálený přístup přes tunel

Aplikace běží na uživatelově počítači (SQLite, data na disku, Hook control, lokální
modely) a ven vede jen tunel na `127.0.0.1:8740`. Backend je v tomto režimu jen tehdy,
když má obě proměnné `OPORA_PUBLIC_HOSTS` a `OPORA_ACCESS_TOKEN`; jinak platí výhradně
loopback. Pro veřejný Host pak platí:

- každý `/api/*` (i GET) vyžaduje `Authorization: Bearer <token>` nebo cookie
  `opora_access`; bez něj přijde 401 `{"error": "Přístup vyžaduje token."}`,
- Origin se porovnává proti `https://HOST` (schéma z `X-Forwarded-Proto`),
- `/api/access/status` (bez tokenu), `POST /api/access/login {token}` a
  `POST /api/access/logout` obsluhují přihlášení prohlížeče,
- `/api/agent-hooks/event`, `/api/agent-hooks/ack`, `/api/assistant/*` a `/api/rlm/*` vrací
  zvenčí **403 i s tokenem**; řídí procesy a klíče na tom počítači, ne u vzdáleného agenta.

Token drž jen v proměnné prostředí `OPORA_ACCESS_TOKEN`, nikdy v příkazu, souboru,
poznámce ani ve výstupu. Čtecí skript ho pak použije sám:

```bash
python "<SKILL_DIR>/scripts/opora_read.py" --api-base https://JMENO.trycloudflare.com view --project ID --workspace draft
```

Adresa quick tunelu se mění při každém spuštění; starou nepoužívej jako důkaz identity.
Kdo má URL i token, má plný zápis — zachází se s ním jako s heslem. `docs/vzdaleny-pristup.md`.

## Zápis — až na konkrétní uživatelův požadavek

Backend přijímá lokální Host `127.0.0.1:PORT` nebo `localhost:PORT` (a v režimu tunelu
i povolený veřejný Host, viz výše). Pro POST vyžaduje `Content-Type: application/json`
a **Origin shodný s http://Host** (přes tunel `https://HOST`).
`localhost` a `127.0.0.1` v Origin nelze libovolně míchat.
403 není povel obejít kontrolu: oprav adresu a formát požadavku.

| POST | Přesná důležitá pole payloadu |
|---|---|
| `/api/node-text` | project, workspace, node, `expected_revision`, text |
| `/api/node-spec` | project, workspace, node, `expected_revision`, fields `{goal, non_goals, acceptance}` |
| `/api/node-journal` | project, workspace, node, záznam |
| `/api/project-settings` | project, nastavení (zadání apod.) |
| `/api/graph` | project, workspace, graph `{nodes, edges}`, `digest` z posledního view, volitelně `undo` (bool, výchozí false) |
| `/api/desktop-v3/state` | project, workspace, `expectedRevision`, state (celý aktuální dokument) |
| `/api/desktop-v3/block` | project, workspace, nodeId, `expectedRevision`, `op: {kind: add\|update\|remove\|todo, ...}` — adresný zápis jednoho bloku |
| `/api/desktop-v3/agent-workspace` | project, workspace, nodeId, `expectedRevision`, `sections: {frame?, log?, failures?, fixes?, handoff?}` (neuvedená sekce zůstává), `by: "human"\|"agent"` — prostor modelu, ne zadání |
| `/api/desktop-v3/packet/preview` | project, workspace, nodeId, path, sessionId, references, note, volitelně `blockId` (aktuální krok balíčku) |
| `/api/desktop-v3/packet/snapshot` | stejná pole jako preview + jeho digest |
| `/api/desktop-v3/packet/snapshots/{id}/external-export` | project, workspace, nodeId, digest snímku |
| `/api/desktop-v3/agent-output` | project, workspace, nodeId, `expectedRevision`, `agent`, `output: {schema: "opora.agent-output/1", blocks: [{blockId, status: met\|unmet\|blocked, note}], reports: [{edgeId, log, summary, handoff, improvements, errors}], done: {proposed, note}, decisions: [text]}`. Výstup modelu. Neznámý blok nebo vazba = 409, uzavřená karta ho odmítne. `blocks[].note` se ověří, ale neuloží; poznámka patří do `reports` |
| `/api/desktop-v3/agent-messages` | project, workspace, sourceNodeId, targetNodeId, `kind: handoff\|question\|answer\|blocker\|result\|correction`, body, replyToMessageId, idempotencyKey, senderLabel. Neměnná zpráva, `identityVerified: false` |
| `/api/desktop-v3/agent-message-receipt` | project, workspace, nodeId (příjemce), messageId, digest (SHA-256 zprávy), `disposition: accepted\|rejected\|needs_clarification`, note, recipientLabel |
| `/api/node-materials/upload` | přesně project, workspace, nodeId, `dataUrl` (obrázek png/jpg/gif/webp/svg, max 8 MB); main odmítne |
| `/api/node-materials/remove` | project, nodeId, file |
| `/api/rlm/rank` | přesně project, workspace, query (1–2000 znaků), `candidates: [{id, text}]` (1–255, id `[A-Za-z0-9_-]{1,128}`, text nad 300 znaků se ořízne), top 1–50. Jen čtení, jen loopback; `{status: ok, ranked}` nebo `{status: unavailable}` |
| `/api/memory/recall`, `/remember`, `/lend`, `/provision`, `/settings` | přesná pole podle `docs/pamet-agentu.md`; `remember` a `provision` vyžadují `confirmed: true` |
| `/api/processes` | project, title, volitelně owner, `by: {kind, name}`, nodeId, sectorId, steps [text], inputs; založí proces |
| `/api/processes/{id}/transition` | project, `revision`, `to: draft\|running\|done\|repair`, `by`, volitelně note, failure, fix |
| `/api/processes/{id}/steps/{step_id}` | project, `revision`, `state: pending\|running\|done\|failed`, evidence (povinný u done/failed) |
| `/api/processes/{id}/reports` | project, `kind: progress\|step_done\|step_failed\|question\|result`, `by: {kind, name}`, `summary` (1–4000 znaků), `processRevision`, u kroku `stepId`, u selhání `error`, volitelně `outputs: [{kind: json\|db\|md\|file, ref}]`. `step_done` uzavře krok s důkazem, `step_failed` přepne proces do opravy |
| `/api/local-project` | `{name, path, confirmed: true}`, kde `path` je absolutní cesta k originální složce (viz navigation.md) |
| `/api/remove` | project, workspace, kind, target, `digest` z `/api/removal-preview`, `confirmed: true`. Odpojení projektu jen archivuje, soubory zůstanou |
| `/api/node-sessions/bind` | přesně project, workspace, nodeId, `source: hermes\|claude`, sessionId, runId, `role: orchestrator\|worker`, title, parentSessionId, `confirmed: true`. Hermes: `runId: null`; Claude: `runId` = název lane. `parentSessionId` je `null` nebo ID jiné session. Prázdný řetězec neprojde |
| `/api/agents/bindings` | vazba agentní telemetrie; payload ověř v `backend/api/live_run/agent_routes.py` |

Pole `expected_revision` a `expectedRevision` mají různý zápis podle endpointu.
Neopravuj jej „sjednocením“. Žádný endpoint popsaný zde nespouští ani nezastavuje model. Výjimkou je `/api/assistant/*` (chat v okně aplikace, jen loopback, spouští ho člověk; kontrakt `docs/asistent.md`). Agent ho nevolá.

`undo: true` na `/api/graph` je krok zpět plátna (Ctrl+Z), ne mazání: pustí snímek, ve kterém
uzel nebo vazba chybí, ale žádný obsah nemaže — text, zadání, deník, kresba, stav Desktop v3
i prostor agenta zůstávají, takže návrat stejného ID kartu vrátí i s obsahem. Snímek musí být
konzistentní (žádná osiřelá vazba, žádný potomek bez rodiče). Skutečné odstranění má vždy
náhled a potvrzení přes `/api/removal-preview` + `/api/remove`; `undo` ho nenahrazuje.

### Recept: přidat pravidlo bez ztráty ostatních dat

Níže je postup, ne automaticky schválený zápis. Hodnoty doplň z aktuálního úkolu:

1. GET `/api/desktop-v3/state?project=...&workspace=...`.
2. Je-li readOnly, zastav. Uchovej celé state a revision.
3. Zkopíruj celé state a přidej **jedno** pravidlo do `rules`:
   `{id: nové UUID, text: schválené znění, kind: "must" nebo "must_not",
   scope: "project" / "path" / "node", target: "" nebo skutečná cesta/ID}`.
4. POST nový celý dokument s původní `expectedRevision`. **Sekvenčně** —
   současný whole-state zápis z jiné karty/agenta může vytvořit konflikt.
5. GET stejný scope, vyhledej ID pravidla a porovnej obsah. Zkontroluj, že
   ostatní pravidla/nastavení/rozhodnutí/uzly/tickety nezmizely.
6. Při 409 nerecykluj starý dokument s novou revizí: načti nový stav,
   znovu aplikuj jen tuto změnu; významový konflikt předej uživateli.

### Recept: konceptový uzel bez filesystem oprávnění

1. GET view; vyber existující rodičovský sektor ID a ověř readOnly=false.
2. Zachovej všechny nodes/edges; přidej objekt s přesnými poli
   `id, parentId, kind: "node", name, purpose, x, y`. Konceptu **nepřidávej sourceRef**.
3. ID musí odpovídat `[A-Za-z0-9_-]{1,80}`; použij nově vygenerované UUID.
   Jméno je neprázdné, nejvýše 160 znaků; purpose nejvýše 12000. Souřadnice
   jsou konečná čísla; zvol pozici podle skutečné vrstvy, ne náhodným přepsáním layoutu.
4. POST graph s původním digestem, potom GET view; ověř ID, parentId a absenci sourceRef.
5. Selže-li validace, neodstraňuj ji. Ověř současná pravidla v `backend/canvas/graph.py`.

Připojení projektu, existujících souborů, kreslení a mazání mají vlastní
rozsáhlejší kontrakty. Neodhaduj payload. Načti cíleně jejich frontend
volání a backend podle `source-map.md`, nebo proveď operaci přes autorizované UI.

## Oracle: echo, verdikt a OporaHub

Jen čtení, pokud není řečeno jinak. Kontrakt je `docs/synchronizace-pravdy.md`.

- `GET /api/sync-report?project=&workspace=` — echo (nerovnosti mezi zadáním, kódem a
  gitem) a verdikt každého rozsahu: `canCommit`, `canMerge`, kontroly brány a další krok.
  Nic nespouští; běh trvá jednotky sekund, protože čte historii gitu.
- `POST /api/check-run` `{project, workspace, scope, sha, status: "green"|"red", detail}` —
  zapíše výsledek běhu kontrol k jednomu commitu. Aplikace testy nespouští, jen zapisuje
  výsledek. `GET /api/check-run?project=&workspace=&scope=` vrací poslední záznam.
- `POST /api/opora-commit` `{project, workspace, scope, subject, by}` — commit zadání
  v OporaHubu. Obsah (revizi zadání a otisk grafu) si backend vezme ze svého stavu.
  `by.kind` musí být `human` nebo `orchestrator`; **agent zapsat nesmí** (409).
- `GET /api/opora-commits?project=&workspace=&scope=&limit=` — historie, hlava a main.
- `POST /api/opora-merge` `{project, workspace, scope, id, by}` — merge commitu do mainu
  OporaHubu. Projde jen tehdy, když má rozsah `canMerge`; jinak 409 se seznamem kroků.

