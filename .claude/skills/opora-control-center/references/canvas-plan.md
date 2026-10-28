# Stavba plátna: dávka plánu, rozšíření, graf, rozmístění

Kdy mě číst: zakládáš sektory a karty, přidáváš bloky / porty / vazby / pravidla k existujícím
kartám, nebo přeskládáváš oblast. Co má dobrá karta obsahovat: [workflow.md](workflow.md) „Laťka karty“.

## Dávka `/api/canvas-plan` (výchozí cesta)

Jedna dávka = jedna oblast nebo sektor, do ~25 kB. Jen přidává a je atomická: projde celá, nebo nic.

1. `opora_read.py view` → `digest`.
2. Koncept zapiš **jednou a bez `dryRun`** do souboru (`<draftsDir>/plan.json`):

<!-- example: /api/canvas-plan -->
```json
{"digest": "DIGEST",
 "plan": {
   "nodes": [
     {"ref": "vlna-2", "kind": "sector", "parent": null, "name": "Vlna 2", "purpose": "Zpracování dokumentů",
      "gateNodeId": "overeni",
      "spec": {"goal": "Dokumenty projdou ingestem a chunkingem", "non_goals": "Retrieval řeší Vlna 3",
               "acceptance": "Všechny karty uzavřené, E2E scénář prošel"}},
     {"ref": "ingest", "kind": "node", "parent": "vlna-2", "name": "[task] Ingest dokumentů",
      "purpose": "Přijme soubory a uloží je", "text": "Zadání, kap. Zpracování dat: …",
      "sourceRef": {"origin": "planned", "path": "", "kind": "directory"},
      "card": {"layer": "backend", "status": "ready", "model": "opus", "effort": "high",
               "tech": "FastAPI + SQLAlchemy", "states": ["čeká", "ukládá", "chyba", "hotovo"]},
      "checks": [{"id": "unit", "command": "uv run pytest backend/ingest"}], "goal_mode": "until_checks_pass",
      "spec": {"goal": "Soubor se uloží s metadaty", "acceptance": "uv run pytest backend/ingest projde"},
      "blocks": [{"ref": "formaty", "title": "Formáty vstupu", "text": "PDF, DOCX, HTML", "condition": "Každý formát má test",
                  "ports": [{"ref": "ok", "label": "Splněno → chunking"}]}],
      "rules": [{"kind": "must", "text": "Každý záznam nese organizaci a projekt."}]},
     {"ref": "chunking", "kind": "node", "parent": "vlna-2", "name": "[task] Chunking", "purpose": "Rozdělí text"},
     {"ref": "overeni", "kind": "node", "parent": "vlna-2", "name": "[task] Ověření sektoru", "purpose": "E2E proti DB"}
   ],
   "edges": [
     {"from": "ingest", "to": "chunking", "port": "block", "block": "formaty", "blockPort": "ok"},
     {"from": "chunking", "to": "overeni", "port": "next", "carries": "data"}
   ],
   "decisions": [{"node": "ingest", "text": "Ukládáme originál i extrahovaný text.", "pinned": false}]
 }}
```

3. Ověř bez zápisu: `opora_write.py /api/canvas-plan --project P --workspace W --json-file "<draftsDir>/plan.json" --dry-run`.
4. Ostře tentýž příkaz bez `--dry-run` (v okně OPORA člověk schválí jednou). Koncept kvůli tomu nepřepisuj.
5. Odpověď: `{ok, refs {ref → id}, blocks {"ref/blokRef" → blockId}, summary, warnings, digest, revision}`.
   ID z `--dry-run` jsou jen ukázkové. Zkontroluj `node-brief` nových karet.
   `warnings` `[{rule, message, nodeId?, place?}]` (≤ 20, i u `--dry-run`): díry kontroly mapy, které dávka
   **otevřela** (byly po ní, ne před ní); `place` = karta, kde se díra řeší. Dávku neodmítají; zacel je další
   dávkou nebo je uveď v souhrnu. Díry, které už existovaly, sem nepatří.

Pravidla dávky:

- Požadavek: `digest`, `plan`, `dryRun?`. `plan`: `nodes`, `edges`, `decisions`, `extend`. ≤ 200 uzlů, 600 vazeb, 2 MiB.
- Uzel: `ref` (`[a-z0-9-]` ≤ 80), `kind` (`node`, `sector`, `comment`, `area`), `name` (≤ 160).
  Volitelně `parent`, `purpose`, `sourceRef`, `spec`, `text`, `card`, `blocks`, `rules`, `criteria`,
  `agentRole`, `checks`, `goal_mode`, `scenario`, `design`, `factRefs`, `downloadsUrl`, `gateNodeId`
  (sektor), `size` a `color` (oblast), `site`, `position`, `fragmentRef`. Bez `position` rozmístí backend.
- `fragmentRef` (jen `node` a `sector`): odkaz do schránky zadání `{fragmentId, revision?}` nebo pole 1–50 odkazů;
  bez `revision` poslední revize. Fragment musí existovat v tomtéž projektu a prostoru (jinak 409). Karta pak
  v `node-brief.fragments` dostane doslovný text a `changedSinceInsert`; schránka ji počítá jako „vloženo“.
- `parent` a konce vazeb: `ref` z dávky, `"@<id>"` existujícího uzlu, nebo `null` (kořen).
- Vazba: `from`, `to`, `port` `next` (výchozí) | `action` | `rule` | `block` | `flow`. `block`
  vyžaduje `block` + `blockPort` zdroje; `flow` jen mezi oblastmi; komentář bez vazeb.
  Volitelně `carries` (co po vazbě teče): `navigation` | `data` | `command` | `event`, jen u `next`
  (jinak 409). Neuváděj ho, když druh toku neznáš; server ho nikdy nedoplní.
- `card`: `layer` `frontend|backend|database|library`, `status` `draft|ready`, `due` `YYYY-MM-DD`,
  `model` `fable|opus|sonnet|haiku`, `effort` `low|medium|high|xhigh|max`. Nikdy `{}`.
  Komponenta: `tech` (technologie, 1–80 znaků) a `states` (1–8 různých stavů po 1–40 znacích, např.
  `prázdno`, `načítá`, `chyba`, `hotovo`); bez okrajových mezer, prázdné vynech. Odesílá-li komponenta data, dej jí stav `chyba`.
  Komponenta pod stránkou: `section` = id sekce ze `site.sections` **nejbližší stránky** mezi předky karty, kterou
  realizuje (např. `"card": {"layer": "frontend", "section": "form"}`). Neexistující sekci i sekci u karty mimo
  stránku server odmítne (409 s důvodem); sekci, kterou neznáš, vynech.
- `site` stránky smí nést sekce `[{id, role, name, intent, moves?}]` (1–20; `intent` 0–200). `moves` (1–120) říká,
  čím sekce posouvá zákazníka v kroku cesty („Rozptýlí obavu ze spamu: jen e-mail.“); neznáš-li ho, vynech, prázdné
  server odmítne (422). Sekce jsou zadání stránky: jejich změna mění `contextVersion` stránky i komponent pod ní.
- Aplikace (sektor): `site: {kind: "application", environments: [{name, host}], healthPath?, journeys?}`; pole je
  `environments` (seznam), ne `environment`. Stránka (uzel pod aplikací): `site: {kind: "page", path, goal?, feel?,
  navLabel?, sections?}`. Cesta `journeys: [{id, name, steps: [{id, page, via?, label?, shift?, objection?}]}]`
  (2–30 kroků): `page` je **ref stránky v dávce** (server ho přeloží na id), `@id` existující stránky, nebo `nav`
  jen u prvního kroku; URL cesta (`/pribeh`) tam nepatří. Další krok nese `via: {do: "click"|"submit", text?, section?}`.
- Neplatný `site` vrací 422 s `field` (např. `site.journeys[0].steps[1].page`), `expected` a platným `example`.
- Typ karty je předpona názvu: `[task]`, `[research]`, `[prototype]`, `[grilling]`, `[gate]`.
- GOAL: `goal_mode: "until_checks_pass"` + aspoň jedna `checks`. Po vytvoření mění `checks`,
  `goal_mode` a `gateNodeId` jen člověk.
- Chyba nese jméno položky (`ingest.blocks[0]: …`). Oprav novým menším konceptem jen s dotčenou částí.

`sourceRef`: `{origin: existing|planned, path, kind: directory|file}`. Karta se zdrojem leží
v sektoru; sektor smí mít jen `directory`. `existing` musí na disku existovat a ležet pod cestou
sektoru; `planned` s prázdnou cestou projde vždy. Komentář a oblast `sourceRef` nemají.

## Rozšíření existujících karet (`plan.extend`)

Položka `{node: "@id", expectedRevision, …}` (revize ze `state`), každá karta jednou, ≤ 200 položek:

- `blocks` (stejný tvar jako u nové karty, přidají se za poslední číslo),
- `ports: [{block: "<blockId>", ports: [{ref, label}]}]`, `rules: [{kind, text}]`,
- `spec: {expectedRevision, fields: {goal?, non_goals?, acceptance?}}` (doplní jen uvedená pole),
- `text: {expectedRevision, text}` (nahradí celý text),
- přesun do oblasti `{parent: "@oblast", columns}`, barva oblasti `{color}`,
- `fragmentRef` (stejný tvar jako u nové karty): přidá odkazy do schránky; odkaz na týž fragment přepíše revizi, ostatní zůstanou.
- `layer`, `tech`, `states`, `section` (jen uzel): přepíší `card.layer` / `card.tech` / `card.states` / `card.section`;
  `null` u `tech`, `states` a `section` je smaže. `section` musí být sekce nejbližší stránky, jinak 409.

```json
{"digest": "DIGEST", "plan": {"nodes": [], "edges": [], "extend": [
  {"node": "@NODE_ID", "expectedRevision": 41,
   "fragmentRef": [{"fragmentId": "FRAGMENT_3_36"}, {"fragmentId": "FRAGMENT_3_37"}]}]}}
```

Hrana ve stejné dávce může mít `from: "@id"`, `block: "<ref nového bloku>"`, `blockPort: "<ref portu>"`.
Výsledek vrátí `blocks["@id/ref"]`.

## Port, který založí navazující kartu

Port může nést `onMet: {"kind": "spawn", "template": {"name": "[task] Review", "spec": {"goal": "…"}, "text": "…"}}`
(šablona: `name, purpose, spec, text, checks, goal_mode`). Když blok přejde do `met`, server založí
sourozeneckou kartu a vazbu z portu (jednou na kombinaci karta/blok/port). Zápis vrátí `graphChanged: true`.

## Celý graf `/api/graph` (jen na úpravu existujícího grafu)

`view --raw` → zachovej **všechny** uzly a vazby, změň jen svou část, pošli `{digest, graph}`.
Chybějící uzel nebo vazba = mazání a backend ho odmítne (mazání dělá člověk v UI s náhledem).
Uzel: `{id, parentId, kind, name, purpose, x, y, sourceRef?, card?, design?, factRefs?, scenario?}`.

## Rozmístění `/api/canvas-layout`

`{digest, area: "@oblast", order: ["@karta", …], columns: 1–20, color?, dryRun?}`. Backend ověří
místo a kolize a přenese karty do oblasti; `dryRun` vrátí graf a SVG bez zápisu.
Náhled vrstvy: `opora_read.py layout-preview [--node SEKTOR]`.

## Další data na kartě

- `design: {artifactUrl, version, previewUrl?}`: odkaz na návrh obrazovky; `previewUrl` jen https na veřejný host.
- `factRefs: [settingId]`: odkaz na fakta projektu (`state.settings`); hodnoty brief rozliší v `context.usedFacts`.
- `scenario: {command}` u `[gate]` karty: uzavření brány chce úspěšný `scenarioRun` (viz [legacy.md](legacy.md)).
- `downloadsUrl: true`: karta stahuje obsah z URL; vznikne blok „Bezpečnost vstupu“ (SSRF, DNS, limity), který musí být `met`.
