# Stopa práce karty

Krok 1b kontraktu [panel bloku](navrhy/2026-10-31-panel-bloku.md) („Co OPORA o práci na kartě ví“, „Kdo panel
plní“), první řez, jen backend. Stopa je **projekce při čtení**: nové úložiště ani změna schématu nevzniká,
model se nevolá, nic se nezapisuje.

```
GET /api/oporahub/card-trail?project=&workspace=&node=
```

Identita jako u historie exekucí (člověk s relačním dokladem UI, nebo agent s `X-Opora-Actor`), jinak 428
`identity_required`. Neplatný rozsah nebo `node` vrátí 409 `card_trail_unavailable`.

Kód: `backend/canvas/card_trail_read.py` (sběr faktů), `backend/canvas/card_trail.py` (čistá projekce),
`backend/canvas/card_trail_judgment.py` (příznaky), router `backend/api/editor/card_trail_routes.py`.

## Odpověď

```json
{
  "nodeId": "n0",
  "now": {"owner": "agent:builder", "since": "2026-10-31T11:00:00Z", "until": "2026-10-31T12:00:00Z",
          "stepId": "s2", "source": "det"},
  "runs": [{"executionId": "e1", "taskId": null, "owner": "agent:builder", "createdAt": "…", "until": "…",
            "state": "reported", "summary": "Doplnil test.", "source": "agent", "attempts": 1, "reported": true,
            "steps": [{"stepId": "s1", "title": "Test modulu", "status": "done",
                       "checks": [{"name": "npm test", "status": "green"}], "commits": ["a…"],
                       "notes": "test x", "source": "agent", "files": ["backend/x/a.py"],
                       "allowed": ["backend/x/**"]}]}],
  "pr": {"number": 7, "state": "open"},
  "missing": ["merged", "human_close"],
  "recent": [{"at": "…", "who": "builder", "label": "Krok hotový", "kind": "step.done", "source": "det"}],
  "ports": [{"edgeId": "e1", "targetId": "n1", "targetName": "Karta 1", "summary": "Hotové API",
             "handoff": "Použij /x", "by": "builder", "updatedAt": "…", "source": "agent"}],
  "judgment": [{"code": "files_mismatch", "stepId": "s1", "executionId": "e1", "outside": ["docs/a.md"],
                "reason": "Commit mění 1 souborů mimo soubory kroku.", "source": "det"}],
  "filesKnown": true
}
```

| pole | odkud |
|---|---|
| `runs[]` exekuce | `opora_executions` karty (nejvýš 10, nejnovější první), stav jako v `GET /executions` (`response`), výsledky (`summary`, `stepResults`, `selfChecks`) a průběžné kroky (`POST /steps`); výsledek přepíše průběžný krok |
| `runs[]` úkoly brány | `heart_tasks` karty (nejvýš 10): jeden krok = úkol, `report.sha` = commit, `report.checks`, `body.files` = `allowed`, `attempts` = červená hlášení; `owner` = poslední dělník v událostech `gate.task` |
| `steps[].checks` | jména z `evidence.checks`, stav z `selfChecks` výsledku (`passed` = `green`, `failed` = `red`, jinak `unknown`) |
| `steps[].files` | `git show --name-only` commitů v repozitáři prostoru (`source_root`, jinak `repository_path`); nejvýš 20 commitů na stopu; bez známého repa pole chybí a `filesKnown` = false |
| `steps[].allowed` | `files` kroku plánu z připnutého zadání běhu, u úkolu brány `body.files` |
| `now` | běžící exekuce (`owner`, `createdAt`, `expiresAt`), jinak úkol brány ve stavu `assigned`; `stepId` = první nehotový krok |
| `pr` | odkaz PR karty (`link_for`: sloučený vyhrává), i u zavřené karty |
| `missing` | jediná definice hotovo (`done_state`, stejné díly jako `closure_gate`), karta bez kroků `["steps"]` |
| `recent` | posledních 200 událostí karty (bez `lease.heartbeat`) + posledních 200 úspěšných zápisů záznamu činnosti s kartou, sloučeno, nejnovějších 10 |
| `ports` | vazby z karty (`source == node`) a zpráva `state.edges[edgeId]` |

## Původ textu (`source`)

- `det` – odvodil kód (popisky událostí a záznamu činnosti, šablony důvodů, prázdné texty);
- `agent` – napsal dělník (shrnutí běhu, `notes` kroku, zpráva na vazbě, popisek události z cizího zdroje);
- `heart` – napsalo srdce (`owner` / `agent` = `heart`);
- `human` – zprávu na vazbě napsal člověk (`by: human`); oproti kontraktu čtvrtá hodnota, jinak by se lidský
  text tvářil jako dělníkův.

U kroku `source` říká původ `notes`; stav, kontroly, commity a soubory jsou vždy záznam.

## Příznaky „potřebuje úsudek“ (`judgment`)

| `code` | kdy |
|---|---|
| `red_twice` | kontrola kroku červená (nebo krok `failed`) ve ≥ 2 bězích; u úkolu brány `attempts` ≥ 2 |
| `delivered_without_evidence` | nejnovější hlášení `done` kroku nemá kontrolu ani commit |
| `missing_summary` | skončený běh s odevzdaným výsledkem a prázdným shrnutím |
| `files_mismatch` | soubory commitů nejnovějšího `done` mimo `allowed` (glob, `*` i přes `/`, složka `x/`); jen když jsou známé obě strany |

Příznaky **nejsou napojené na srdce** (snímek, prompt, supervisor beze změny). Napojení je další, zvlášť
měřená změna (lekce m11: měnit, co srdce dostává, po jedné).

## Mimo první řez

- události `tool.use` z hooku relace dělníka (krok 1b, druhá část) – až přijdou s `nodeId`, objeví se v `recent`
  samy, zdroj `agent`;
- UI panelu (návrh přes Claude Design).
