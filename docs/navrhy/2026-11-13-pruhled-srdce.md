# Průhled srdce: co dělá, proč čeká, kde se zastaví a čím to ovlivnit (2026-11-13)

Zadání člověka: „ať se to dá dohledat u srdce, … kde bude vidět jak pracuje a bude se to dát ovlivnit. Potřebuji
vědět, co, jak, proč dělá, kde se to může zastavit, ať je pro ostatní agenty čitelný.“

## §0 Milníky a body hotovo

| Milník | Hotovo, když | Důkaz |
|---|---|---|
| M1 Srdce nečeká na zámek (OP-A3AE94) | agent-state Ample na kopii dat výrazně rychlejší se stejným výstupem; zápisy srdce nepadají na 60 s | měření před/po, `cmp` výstupů, pytest |
| M2 Průhled pro agenty (`GET /api/pletor/heart/explain`) | JSON i `format=text` říká stav jednou větou, frontu, zarážky, tok s časy uzlů a rozpad dávek | testy `test_heart_explain.py`, `test_heart_phases.py`, živé volání |
| M3 Ovládání a Velín | Velín → Srdce ukazuje totéž a člověk mění stropy (`PUT /api/pletor/heart/caps`) | `npm test`, `npm run build`, náhled |
| M4 Čitelné pro ostatní agenty | `opora_hub.py heart` vypíše průhled; skill na něj ukazuje | test skriptu, výpis |

Naměřeno po M1 naživo (13. 11.): první dávka Ample 85 s, zápis 19 s (dříve 213–613 s); dávka 01:42 114 s, zápis 80 %,
`brief` 30 s a jednou timeout 60 s, tedy zámek se pod zátěží ještě občas drží. Na kopii dat agent-state 65 s → 8–17 s
se shodným výstupem. Další dávky sleduje zarážka `lock` (zápis ≥ 50 % dávky nebo snímek > 30 s).

Poctivý východ: co nejde dokončit, se zapíše jako blokace v tomto dokumentu (§6) a v hlášení, ne čekáním.

## §1 Co jsme naměřili (výchozí stav)

- Dávka srdce Ample trvala 213–483 s. Čtení podkladů zabralo jen jednotky sekund.
- 50–85 % dávky srdce čekalo na **zápis do OPORY** (`opora_heart.py steps|order|answer|intake`): 94–222 s na jeden
  příkaz, opakovaně `server_unreachable` po 60 s (limit CLI srdce).
- Příčina: `GET /api/oporahub/agent-state` Ample se stavěl 65 s (124 s pod profilerem) a celou dobu držel zámek
  projektu (`graph_lock_for` + `lock_for`). Agenti ho čtou často, zápisy srdce (`changesets/context` 99,5 s, z toho
  výpočet 0,2 s) čekaly ve frontě na zámek. Uzel toku `snimek` čekal 118 s ze stejného důvodu.
- Mezi dávkami platí strop 6 automatických dávek za hodinu (`per_hour` uzlu `agent.claude`); zpráva člověka ho obchází.

## §2 Kam šel čas dávky (`heart_phases.py`)

Kroky dávky (`steps.py`: `tool` / `result` / `text` / `thinking` s časem `t`) se rozpadnou na fáze: čas mezi kroky
patří nejstaršímu otevřenému nástroji, jinak modelu. Fáze: model (vč. poradce), čtení podkladů z OPORY, zápis do OPORY,
čtení kódu, příprava souborů, jiné příkazy, podagenti. K tomu nejpomalejší volání a selhání s kódem chyby.
Je to odhad z časů kroků; deník drží nejvýš 80 kroků (`truncated`).

## §3 Kde se srdce zastaví (`heart_stops.py`)

Pevný seznam zarážek, u každé `active`, příčina a páka: vypnuté srdce, vypnutá brána, strop za hodinu, spánek po limitu
předplatného, chyba toku, chyba gitu, zápisy srdce čekají na server (zámek projektu nebo jiná práce; kdo, ukazují pomalé požadavky), zápis vypršel (60 s), neexistující příkaz
(skill srdce ≠ nástroj), krok patří člověku.

## §4 Páky

- Stropy `per_hour` (1–60), `per_project` (1–4), `rate_sleep_seconds` (60–10800): `PUT /api/pletor/heart/caps`, jen člověk,
  nová verze sdíleného toku Srdce v1 (platí pro celou aplikaci od dalšího průchodu plánovače).
- Model, poradce a effort: `PUT /api/pletor/heart/model` (beze změny).
- Zpráva člověka obchází strop za hodinu; brána a autonomie ve Velínu → Autonomie.

## §5 Rozhraní

`GET /api/pletor/heart/explain?project=<id>[&format=text]` čte agent i člověk (jen čtení, žádný zámek projektu):

```text
{now: {state: running|sleeping|window|hour_cap|starting|idle|off, sentence, until?, since?},
 queue: [{type, ref, workspace, dueAt, dueInS}], stops: [{id, label, active, detail, lever}],
 pipeline: [{run, status, at, nodes: [{node, label, status, ms, error}]}],
 batches: [{at, status, summary, inputs, costUsd, numTurns, headline, phases, slowest, failures, truncated, durationMs}],
 caps: {per_hour, per_project, rate_sleep_seconds, bounds}, model: {...}}
```

## §6 Blokace a vynechané

- Skill srdce v Brainu volá `escalate`, který `opora_heart.py` už nemá (exit 2). Patří práci jiné relace (OP-33C186,
  srdce bez dotazů na člověka); průhled ji ukazuje zarážkou `unknown_command`, neopravuje ji.
- M4 jen zčásti: `GET /api/brain/heart/status` nese odkaz `explain` na textový průhled, takže ho agent najde ze stavu
  srdce. Příkaz `opora_hub.py heart` a odkaz ve skillu nejsou: seed skillu `opora-control-center` má v pracovním stromu
  rozdělanou změnu jiné práce a kopii seedu do Brainu dělá člověk.
- Zámek projektu pod zátěží: když se zarážka `lock` vrátí, hledat držitele zámku (další dlouhé čtení pod
  `graph_lock_for`/`lock_for`), ne zvyšovat timeout CLI srdce.
- `per_project` je pevně 1: srdce má na projekt jeden soubor relace a jeden slot běžící dávky.
- Dávka 01:42 (po M1): `brief` čekal 60 s a při opakování 30 s, srdce souběžně nic nevolalo a výpočet trvá 0,8 s.
  Zahřátý agent-state drží zámek 0,4–1,3 s (3 souběžná čtení, zápisová cesta 0,43 s), server byl 4 min po restartu
  (studené čtení 18 s). Držitele nešlo zpětně určit, proto průhled od OP-0A8666 vede **pomalé požadavky serveru**
  (`backend/app/slow_requests.py`: požadavky nad 5 s, kruhová paměť procesu, po restartu prázdná).
