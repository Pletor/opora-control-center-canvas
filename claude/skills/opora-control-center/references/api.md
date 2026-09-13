# API — přesný scope, čtení a bezpečný zápis

Toto je příručka pro autorizovanou práci přes HTTP, ne univerzální admin API.
Pomocný `scripts/opora_read.py` záměrně podporuje jen GET; nic nemění a nic nespouští.

## Spuštění skriptu

```bash
python "<SKILL_DIR>/scripts/opora_read.py" --help
python "<SKILL_DIR>/scripts/opora_read.py" --base-url http://127.0.0.1:8780 workspaces --project ID
python "<SKILL_DIR>/scripts/opora_read.py" --base-url http://127.0.0.1:8780 capabilities --project ID
python "<SKILL_DIR>/scripts/opora_read.py" --base-url http://127.0.0.1:8780 node-spec --project ID --workspace ID --node ID --raw
python "<SKILL_DIR>/scripts/opora_read.py" --base-url http://127.0.0.1:8780 run --project ID --workspace ID --id RUN_ID
python "<SKILL_DIR>/scripts/opora_read.py" --base-url http://127.0.0.1:8780 snapshot --project ID --workspace ID --id SNAPSHOT_ID
```

Výstup je JSON na stdout. Návratový kód 0 = požadované čtení uspělo;
1 = chybný vstup / nedostupnost; 2 = částečně nedostupné zdroje seznamu runs.
Kód 0 neznamená úspěšné splnění uživatelského úkolu. Skript odmítá vzdálené
adresy, redirecty a proxy a omezuje velikost odpovědi. Nečte env ani credentials.

`run` a `export` jsou pro dokumentační TaskHandoff, nikoli pro ID LLM návrhu.
Po readbacku snapshotu porovnej očekávané ID, digest a node s uloženým zadáním;
skript sám nezná očekávaný digest. `--raw` je plný obsah, nikoli redaktor tajemství.

## Čtení — doložené routy

| GET | Parametry / použití |
|---|---|
| `/api/health` | identita Opora Canvas a dostupnost |
| `/api/build-identity` | identita backendu **při startu**, ne nového statického buildu |
| `/api/bootstrap` | `draft`, `projects`, `jobs`; žádné `/api/projects` nepředpokládej |
| `/api/project-workspaces` | project |
| `/api/view` | project, workspace; `graph`, `digest`, `readOnly` |
| `/api/node-text` | project, workspace, node |
| `/api/node-spec` | project, workspace, node |
| `/api/node-spec/history` | project, workspace, node |
| `/api/drawing` | project, workspace, layer |
| `/api/wireframe-context` | project, workspace, layer |
| `/api/desktop-v3/state` | project, workspace; revision, state, readOnly |
| `/api/task-handoffs/capabilities` | project |
| `/api/task-handoffs` | project, workspace; `runs` |
| `/api/task-handoffs/{id}` | konkrétní handoff; ověř scope odpovědi |
| `/api/task-handoffs/{id}/export` | přesné zadání; ověř id/digest/scope |
| `/api/desktop-v3/packet/snapshots/{id}` | project, workspace |
| `/api/llm/capabilities` | dostupnost návrhového provideru |
| `/api/llm/runs` | project; následně filtruj workspace |
| `/api/coding/capabilities` | aktuální hranice implementačního runtime |
| `/api/coding/runs` | project; nezaměň s návrhem nebo handoffem |

## Zápis — až na konkrétní uživatelův požadavek

Backend přijímá lokální Host `127.0.0.1:PORT` nebo `localhost:PORT`. Pro POST
vyžaduje `Content-Type: application/json` a **Origin shodný s http://Host**.
`localhost` a `127.0.0.1` v Origin nelze libovolně míchat.
403 není povel obejít kontrolu: oprav adresu a formát požadavku.

| POST | Přesná důležitá pole payloadu |
|---|---|
| `/api/node-text` | project, workspace, node, `expected_revision`, text |
| `/api/node-spec` | project, workspace, node, `expected_revision`, fields `{goal, non_goals, acceptance}` |
| `/api/graph` | project, workspace, graph `{nodes, edges}`, `digest` z posledního view |
| `/api/desktop-v3/state` | project, workspace, `expectedRevision`, state (celý aktuální dokument) |
| `/api/desktop-v3/packet/preview` | project, workspace, nodeId, path, sessionId, references, note |
| `/api/desktop-v3/packet/snapshot` | stejná pole jako preview + jeho digest |
| `/api/desktop-v3/packet/snapshots/{id}/prepare` | přesně project, workspace, task |
| `/api/task-handoffs/{id}/start` | digest připraveného běhu, confirmed: true **po schválení** |
| `/api/task-handoffs/{id}/stop` | confirmed: true **pro schválené zastavení tohoto ID** |

Nepřenášej digest snapshotu do startu handoffu: připravený handoff vrátí vlastní
identitu/digest. Pole `expected_revision` a `expectedRevision` mají různý zápis
podle endpointu. Neopravuj jej „sjednocením“.

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
5. Selže-li validace, neodstraňuj ji. Ověř současná pravidla v `backend/graph.py`.

Připojení projektu, existujících souborů, kreslení, mazání a coding start mají
vlastní rozsáhlejší kontrakty. Neodhaduj payload. Načti cíleně jejich frontend
volání a backend podle `source-map.md`, nebo proveď operaci přes autorizované UI.
