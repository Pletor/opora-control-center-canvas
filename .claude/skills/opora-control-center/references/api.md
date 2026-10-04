# API — čtení a zápis přes skripty skillu

V okně OPORA (asistent) sahá agent na aplikaci jen dvěma skripty; mimo aplikaci viz SKILL.md „Agent mimo aplikaci“. `opora_read.py` čte (GET a POST jen na
pevné čtecí dotazy), backend ho pustí bez dotazu. `opora_write.py` zapisuje na plátno, každé volání
schvaluje člověk (výjimka: `/api/canvas-plan … --dry-run`). Adresu vlastní instance oba vezmou
z `OPORA_BASE_URL` (loopback `http://127.0.0.1:<port>`), proto `--base-url` nepiš.

Příklady používají `--project <projectId> --workspace <workspace>`; obě hodnoty ber z `<opora_context>`, mimo aplikaci z `opora_read.py projects` / `workspaces`.
Vrstvu a výběr ber z `<opora_context>` zprávy.

## Pravidla příkazu

- Příkaz začíná `python` a hned cestou ke skriptu; cestu s mezerou dej do uvozovek.
- V celém příkazu nesmí být `;` `&` `|` `<` `>` `$` `` ` `` ani nový řádek. Jinak ho backend
  zamítne bez dotazu. Řetězení, přesměrování a jiný Bash neprojde.
- `<SKILL_DIR>` a `<draftsDir>` jsou zástupné: nahraď je skutečnou absolutní cestou (`draftsDir`
  je v `<opora_context>`). Se znaky `<` `>` příkaz neprojde.
- `graphify query …` projde také bez dotazu (čtení).

## Čtení: `opora_read.py`

```bash
python "<SKILL_DIR>/scripts/opora_read.py" <příkaz> [volby]
```

Výstup je JSON na stdout, kód 0 = čtení uspělo, 1 = chyba (JSON na stderr, u HTTP `detail`).
Bez `--raw` vrací souhrn, s `--raw` celou odpověď backendu.

| Příkaz | Volby | Co vrátí (souhrn) |
|---|---|---|
| `status` | — | zdraví, identita backendu při startu, otisk servírovaného indexu, počet projektů |
| `projects` | — | `draft`, `projects [{id, name, sourceKind}]`, `jobsCount` |
| `workspaces` | `--project` | prostory projektu (`/api/project-workspaces`) |
| `view` | `--project --workspace` | `readOnly`, `digest`, počty, `nodes [{id, parentId, kind, name, sourceRef}]`. Celý graf (s `x`, `y`, `purpose`, `card`, vazbami) jen s `--raw` |
| `state` | `--project --workspace` | `revision`, `readOnly`, počty `settings, rules, decisions, nodes, tickets`. Obsah (bloky, pravidla, zprávy na vazbách) jen s `--raw` |
| `node-text` | `--project --workspace --node` | `revision`, délka textu; text s `--raw` |
| `node-spec` | `--project --workspace --node` | `revision`, délky `goal, non_goals, acceptance`; obsah s `--raw` |
| `node-brief` | `--project --workspace --node` | balíček karty `opora.node-brief/1`: cíl, začátek textu karty, fáze, stop podmínky, smyčka. Celý (bloky, vazby, rodiče, děti, `outputContract`) s `--raw`. Kontrakt `docs/karta-pro-agenty.md` |
| `frontier` | `--project --workspace --node SEKTOR` | karty sektoru v `frontier`, `claimed`, `blocked`, `closed`, rozhodnutí sektoru a komentáře (`fog`) |
| `sessions` | `--project --workspace [--node]` | navázané sessions agentů (limit 100), jen telemetrie |
| `snapshot` | `--project --workspace --id` | uložený snímek podkladů: `id, digest, createdAt, scope, warnings, sourceManifest` |
| `search` | `--project --workspace --query [--layer ID]` | nejvýš 20 shod z indexu plátna `{id, name, parentId, kind, address, type, layer, status, kde}` |
| `index` | `--project --workspace [--layer ID]` | karty bez obsahu `{id, name, parentId, kind, chars, address, type, layer, status}` |
| `rank` | `--project --workspace --query [--layer ID] [--top 1–50]` | `{status: ok, ranked [{id, p, name}]}` nebo `unavailable`; postup [rlm.md](rlm.md) |
| `code` | `--project --workspace --path SOUBOR --operation definition\|references\|hover\|documentSymbols [--line N --character N]` | odpověď LSP; jazyk z přípony (jen TypeScript/JS a Python), řádek a znak od nuly |
| `find` | `--project --workspace --query [--path PODSTROM] [--limit 1–20]` | sémantické hledání v kódu projektu |
| `recall` | `--project --workspace --query (--role R \| --node N) [--max-tokens N]` | paměť role; karta bez role vrátí `skipped` |

`search` hledá v korpusu karty (adresa, typ, vrstva, název, popis, zdroj, bloky, kritéria, kroky)
a vazby (konce, zpráva). Bez velikosti písmen a diakritiky, každé slovo musí sedět. Filtry:
`typ:task`, `stav:ready`, `druh:edge`, `vrstva:be` (nebo `backend`). Spec se neprohledává; čti ho
přes `node-spec`. `--layer` nechá jen přímé potomky dané karty či sektoru.

```bash
python "<SKILL_DIR>/scripts/opora_read.py" view --project <projectId> --workspace <workspace>
python "<SKILL_DIR>/scripts/opora_read.py" search --project <projectId> --workspace <workspace> --query "typ:task ingest"
python "<SKILL_DIR>/scripts/opora_read.py" node-brief --project <projectId> --workspace <workspace> --node NODE_ID --raw
```

Pořadí hledání: plátno `search` (nebo `index` → `rank`) → `find` / `code` → graphify → Archify →
`recall` → web.

## Zápis: `opora_write.py`

```bash
python "<SKILL_DIR>/scripts/opora_write.py" <cesta> --project P --workspace W (--json '<json>' | --json-file "<draftsDir>/x.json") [--dry-run]
```

- Cesta je jedna z osmi: `/api/graph`, `/api/node-spec`, `/api/node-text`, `/api/desktop-v3/state`,
  `/api/desktop-v3/block`, `/api/desktop-v3/agent-workspace`, `/api/desktop-v3/agent-output`,
  `/api/canvas-plan`. Jinou skript ani schvalování nepustí.
- `project` a `workspace` doplní skript z voleb; jiná hodnota v payloadu je chyba.
- `--json` jen pro krátký payload bez zakázaných znaků. Delší payload napiš nástrojem `Write`
  jako `*.json` do `draftsDir` z `<opora_context>` (absolutní cesta, jméno bez `:`, do 2 MiB) a pošli
  `--json-file`. Karta schválení ukáže souhrn skutečného obsahu souboru; po schválení ho neměň.
- `--dry-run` jen u `/api/canvas-plan`; u jiné cesty je to chyba.
- Main (`readOnly: true`) je jen pro čtení; zapisuj do pracovního prostoru (výchozí workspace je `main` u git projektu a jinak `draft`).

Návratový kód: 0 = zapsáno (`{ok, route, result}`), 3 = HTTP 409, 1 = jiná chyba.
Backend vrací 409 pro **každou** chybu validace, nejen pro konflikt revize: skript vypíše `conflict`
a skutečný důvod je v `detail` na stderr. Při změněné revizi nebo digestu znovu načti stav a použij
jen svou změnu; při chybě validace oprav payload. Starý dokument s novou revizí neposílej.

| Cesta | Payload (kromě project, workspace) | Revize odkud |
|---|---|---|
| `/api/graph` | `digest`, `graph {nodes, edges}` celý | `digest` z `view` |
| `/api/node-spec` | `node`, `expected_revision`, `fields {goal ≤4000, non_goals ≤8000, acceptance ≤12000}` — všechna tři pole vždy | `revision` z `node-spec` (nová karta 0) |
| `/api/node-text` | `node`, `expected_revision`, `text` (≤ 64000) | `revision` z `node-text` (nová karta 0) |
| `/api/desktop-v3/state` | `expectedRevision`, `state` (celý dokument) | `revision` ze `state` |
| `/api/desktop-v3/block` | `nodeId`, `expectedRevision`, `op` (viz níže) | `revision` ze `state` |
| `/api/desktop-v3/agent-workspace` | `nodeId`, `expectedRevision`, `sections {frame?, log?, failures?, fixes?, handoff?}` (každá ≤ 12000, neuvedená zůstává), `by: "agent"` | revize prostoru karty; prázdný prostor má 0 |
| `/api/desktop-v3/agent-output` | `nodeId`, `expectedRevision`, `agent`, `output` (viz níže) | `revision` ze `state` (`node-brief --raw` → `outputContract.request`) |
| `/api/canvas-plan` | `digest`, `plan`, volitelně `dryRun` | `digest` z `view` |

Pole `expected_revision` a `expectedRevision` se liší podle cesty; nesjednocuj je. Do uzavřené
karty (`done.confirmed`) backend blok, výstup ani prostor agenta nezapíše.

Revizi prostoru agenta čtecí skript neukazuje. Bez jistoty piš do karty přes `agent-output`
(zprávy na vazbách) a prostor nech, pokud nejde o prázdný prostor s revizí 0.

### `op` pro `/api/desktop-v3/block`

Klíče přesně takto:

- `{kind: "add", parentBlockId: "" nebo ID, title, text}`
- `{kind: "update", blockId, patch}` — `patch` ⊂ `{title, text, tags, state, ports}`
- `{kind: "remove", blockId}`
- `{kind: "todo", blockId, todo}` — `todo` je `{kind: "add", text, assignee?}` nebo `{kind: "toggle"|"remove", id}`

ID bloků a úkolů najdeš v `node-brief --raw` nebo `state --raw`.

### `output` pro `/api/desktop-v3/agent-output`

Všech pět klíčů je povinných:

```json
{"schema": "opora.agent-output/1",
 "blocks": [{"blockId": "…", "status": "met", "note": "…"}],
 "reports": [{"edgeId": "…", "log": "", "summary": "…", "handoff": "…", "improvements": "", "errors": ""}],
 "done": {"proposed": false, "note": ""},
 "decisions": ["…"]}
```

`status` je `met`, `unmet` nebo `blocked`. Neznámý blok nebo vazba je chyba a nic se nezapíše.
`blocks[].note` se ověří, ale neuloží; text patří do `reports`. Uzavření karty agent jen navrhne
(`done.proposed`), potvrzuje člověk. `sentAt` a `due` zprávy na vazbě agent neposílá: `sentAt` nastaví
aplikace a `due` nastavuje člověk v panelu vazby.

### Recept: víc karet najednou (dávka plánu)

Víc než pár karet, bloky s porty, vazby, text, spec, pravidla a rozhodnutí jdou jednou dávkou
`POST /api/canvas-plan`. Dávka jen přidává, a to atomicky: buď projde celá, nebo nic.

1. `view` → `digest`.
2. `Write` konceptu **jednou a bez `dryRun`** do `<draftsDir>/plan.json`:

   ```json
   {"digest": "DIGEST_Z_VIEW",
    "plan": {
      "nodes": [
        {"ref": "vlna-2", "kind": "sector", "parent": null, "name": "Vlna 2", "purpose": "Zpracování dokumentů",
         "spec": {"goal": "…", "non_goals": "…", "acceptance": "…"}},
        {"ref": "ingest", "kind": "node", "parent": "vlna-2", "name": "[task] Ingest dokumentů",
         "purpose": "…", "text": "Doslovný výňatek zadání …",
         "sourceRef": {"origin": "planned", "path": "api/src/ingest", "kind": "directory"},
         "spec": {"goal": "…", "acceptance": "…"},
         "blocks": [{"ref": "formaty", "title": "Formáty vstupu", "text": "…", "condition": "…",
                     "ports": [{"ref": "ok", "label": "Splněno, dál chunking"}]}],
         "rules": [{"kind": "must", "text": "Každý záznam nese organizaci a projekt."}]},
        {"ref": "chunking", "kind": "node", "parent": "vlna-2", "name": "[task] Chunking", "purpose": "…"}
      ],
      "edges": [
        {"from": "ingest", "to": "chunking", "port": "block", "block": "formaty", "blockPort": "ok"},
        {"from": "@EXISTUJICI_ID", "to": "ingest", "port": "next"}
      ],
      "decisions": [{"node": "ingest", "text": "…", "pinned": false}]
    }}
   ```

3. Ověření bez dotazu (nic nezapíše):

   ```bash
   python "<SKILL_DIR>/scripts/opora_write.py" /api/canvas-plan --project <projectId> --workspace <workspace> --json-file "<draftsDir>/plan.json" --dry-run
   ```

4. Ostře tentýž příkaz bez `--dry-run`; člověk schválí jednou. Koncept kvůli tomu nepřepisuj.
5. Odpověď `{ok, dryRun, refs {ref → id}, blocks {"ref/blokRef" → blockId}, summary, digest, revision}`.
   Zkontroluj `node-brief` nových karet.

Pravidla dávky (`backend/canvas/canvas_plan*.py`):

- Požadavek smí mít jen `digest`, `plan`, `dryRun` (+ project, workspace). `plan` jen `nodes`, `edges`,
  `decisions`; prázdná dávka je chyba. Nejvýš 200 uzlů, 600 vazeb, 2 MiB.
- Uzel: povinné `ref` (`[a-z0-9-]`, do 80, unikátní), `kind` (`node`, `sector`, `comment`, `area`),
  `name`. Volitelné `parent`, `purpose`, `sourceRef`, `size {w, h}` (oblast), `spec` (chybějící pole
  doplní prázdná), `text`, `agentRole`, `blocks`, `rules`. Jiné pole je chyba; `card` ani souřadnice dávka
  nebere (karty položí backend do mřížky pod existující uzly).
- `parent` a konce vazeb: `"@<id existujícího uzlu>"`, `ref` z dávky, nebo `null` (kořen). Rodič-oblast
  znamená „polož dovnitř“; když se karta nevejde, chyba „zvětšete její size“.
- `blocks`, `rules`, `agentRole` jen u `node` a `sector`. Blok: `ref`, `title`, volitelně `text`,
  `condition`, `ports [{ref, label}]`. Pravidlo: přesně `{kind: "must"|"must_not", text}`, scope je karta.
- Vazba: `from`, `to`, `port` (výchozí `next`; dále `action`, `rule`, `block`, `flow`). `block` vyžaduje
  `block` a `blockPort` zdroje (u karty z dávky jejich `ref`, u existující karty ID bloku); u jiného portu
  jsou chyba. `flow` jen mezi oblastmi, komentář bez vazeb.
- Rozhodnutí: `text`, volitelně `node` (ref nebo `@id`), `pinned`.
- Chyba nese jméno položky (`ingest.blocks[0]: …`). Opravu pošli novým menším konceptem jen s opravenou
  částí. Jedna dávka = jedna oblast nebo sektor, nejvýš ~25 kB.

Laťka karty a postup od dlouhého zadání: [workflow.md](workflow.md) „Recept: dlouhé zadání → strom karet“.

### Recept: nový uzel a sektor s kartou (i konceptový uzel)

Pro jednu dvě karty, nebo když je potřeba `card` (dávka ho nebere). `/api/graph` posílá **celý** graf:

1. `view --raw` → celé `graph.nodes`, `graph.edges` a `digest`. `readOnly: true` = zastav.
2. Zachovej všechny záznamy beze změny a přidej nový uzel:
   `{id, parentId, kind, name, purpose, x, y, sourceRef?, card?}`.
   - `id` nové UUID (`[A-Za-z0-9_-]{1,80}`), `kind` `sector` nebo `node`, `parentId` je ID sektoru nebo
     `null`, `name` 1–160 znaků, `purpose` (≤ 12000) vždy, i prázdný, `x`, `y` konečná čísla podle vrstvy.
   - `sourceRef` `{origin: "existing"|"planned", path, kind: "directory"|"file"}`; `existing` musí být
     skutečný soubor či složka zdroje projektu (jinak „Zdroj neodpovídá…“). Konceptový uzel ho nemá.
   - `card` jen u `node`, nikdy prázdné `{}`: `layer` `frontend|backend|database|library`, `status`
     `draft|ready` (`done` dává uzavření karty), `due` `YYYY-MM-DD`, `model` `fable|opus|sonnet|haiku`,
     `effort` `low|medium|high|xhigh|max`. Jiný klíč je chyba.
   - Typ workflow je předpona názvu: `"[task] Přihlášení"` (`research`, `prototype`, `grilling`, `task`).
3. Celý graf zapiš do `<draftsDir>/graph.json` jako `{"digest": "…", "graph": {...}}` a pošli:

   ```bash
   python "<SKILL_DIR>/scripts/opora_write.py" /api/graph --project <projectId> --workspace <workspace> --json-file "<draftsDir>/graph.json"
   ```

4. Zadání nové karty zvlášť (revize 0, všechna tři pole):

   ```bash
   python "<SKILL_DIR>/scripts/opora_write.py" /api/node-spec --project <projectId> --workspace <workspace> --json '{"node": "NOVE_ID", "expected_revision": 0, "fields": {"goal": "Zákazník dostane fakturu", "non_goals": "Neřešit refundace", "acceptance": "Faktura se uloží k objednávce"}}'
   ```

5. Ověř `view` (ID, `parentId`) a `node-spec`.

Graf, ve kterém chybí existující uzel nebo vazba, backend odmítne („Mazání vyžaduje náhled
a potvrzení odstranění“). Mazání, kreslení, připojení projektu a podklady pro agenta (snímek, export)
dělá člověk v UI.

### Recept: přidat pravidlo k existující kartě nebo projektu

Dávka umí pravidla jen u nových karet. Jinak přes celý stav:

1. `state --raw` → `revision`, `state`. `readOnly: true` = zastav.
2. Do kopie celého `state.rules` přidej **jedno** pravidlo
   `{id: nové UUID, text, kind: "must"|"must_not", scope: "project"|"path"|"node", target: "" nebo cesta / ID karty}`.
3. Zapiš `{"expectedRevision": REVIZE, "state": {...celý...}}` do `<draftsDir>/state.json`
   a pošli `/api/desktop-v3/state --json-file`. Zápisy celého stavu jen po jednom.
4. `state --raw` znovu: pravidlo je tam a ostatní pravidla, rozhodnutí a uzly nezmizely.
5. Při 409 s konfliktem revize načti nový stav a přidej jen to jedno pravidlo znovu.
