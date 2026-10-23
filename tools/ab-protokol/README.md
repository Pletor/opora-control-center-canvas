# A/B protokol agentů (simulace)

Porovná dva způsoby, jak agent bere kartu, pracuje po krocích a předává výsledek dál:

- **A — starý protokol** (dnes ho agenti používají): `frontier` → `lease` → `node-brief` →
  úkoly bloků a stav bloku po kroku → `agent-workspace` → `agent-output` → `release` →
  důkazy review a merge dalším `agent-output` → člověk `done.confirmed`.
- **B — OporaHub v2** (napojený, nikdy nespuštěný): návrh kroků (`changesets` s `fields.steps`) →
  člověk přijme → `agent-state` → `executions/context` → `claim` → `assignment` → `heartbeat` →
  `results` se `stepResults` a `selfChecks` → office připojí PR a pošle PR Lens → sloučení →
  zápis plánu → člověk uzavře kartu.
- **B+** — B, kde si agent navíc dočte běhy předchůdců (`executions`, `results`, `pull-request`,
  `review-lens`). Do skóre nevstupuje; dokládá, kolik stojí doplnit předávku do zadání.

Výsledky, rubrika a návrh cílového stavu: [docs/navrhy/2026-10-23-ab-protokol-agentu.md](../../docs/navrhy/2026-10-23-ab-protokol-agentu.md).

## Spuštění

```bash
uv run python tools/ab-protokol/sim.py                 # tabulka výsledků do stdout (markdown)
uv run python tools/ab-protokol/sim.py --json out.json # i úplná naměřená data
uv run pytest tools/ab-protokol -q                     # ~1 min, tři běhy přes skutečný backend
```

`AB_PROTOKOL_TMP=<složka>` přesměruje dočasná data (výchozí systémový temp). SQLite drží soubory
do konce procesu, proto zbytky minulého běhu (`ab-legacy-*`, `ab-hub-*`) smaže až další běh.

## Jak to funguje

- Obě varianty volají **skutečný backend** (`backend.app.factory.create_app`) přes FastAPI
  `TestClient` na dočasné datové složce. Nic nejde na živou aplikaci `:8740` ani do `P:/opora-data`.
- Data: `fixtures/ample-3-karty.json` — tři navazující karty sektoru 1 projektu ample
  (1.3 RAW store → 1.5 Příjem zdroje → 1.6 API zdrojů; bloky, zadání, 31 rozhodnutí projektu)
  a velikosti jejich skutečných `node-brief`. Zkopírováno jen čtením (`GET`), URL vypuštěné.
  V simulaci jsou karty znovu otevřené (bloky `open`).
- Agenti jsou skriptovaní a deterministickí (žádný model). Každý krok udělá skutečný commit
  v dočasném gitu, takže úroveň „kód existuje“ se ověřuje `git cat-file`.
- Jediná simulovaná věc je GitHub ve variantě B: čtení PR vrací hlavu, kterou office ohlásí,
  a sloučení se zapíše jako pozorování rekonciliace (stejně jako backendové testy).
- Každé volání se měří (`ab_meter.Meter`): kdo volal, fáze, bajty požadavku a odpovědi.

| Soubor | Co dělá |
|---|---|
| `sim.py` | spustí A, B, B+ a poruchy, spočítá skóre, vypíše tabulky |
| `ab_meter.py` | prostředí, měřený klient, `create_app` na dočasných datech |
| `ab_repo.py`, `ab_seed.py` | dočasný git a výchozí stav plátna, značky pro měření předávky |
| `ab_legacy.py` | varianta A |
| `ab_hub.py`, `ab_github.py` | varianta B a simulace GitHubu |
| `ab_scenarios.py` | poruchy: souběh, zápis bez oprávnění, změna zadání, pád agenta, opakované odeslání |
| `ab_score.py` | rubrika (váhy předem) a výpočet skóre |
| `test_ab_protokol.py` | kontrola, že harness běží offline a že klíčová zjištění platí |
