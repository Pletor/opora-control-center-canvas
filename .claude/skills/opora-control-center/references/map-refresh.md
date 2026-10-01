# Aktualizace projektových map

Kontrakt: `docs/mapy-projektu.md`. Každý projekt má jednu stabilní sadu map na
pevných cestách, přepisovanou na místě. Neexistují verze, ukazatel ani archiv.

Oba prohlížeče používají jedinou komponentu `MapUpdateMenu`:
- **Aktualizovat teď** — Graphify přímo lokálně, Archify zařadí Sonnet běh.
  Funguje vždy, i při „Pouze ručně“ a i při vypnuté globální automatice.
- **Načíst uložený výstup** — pouze GET, žádný model.
- **Po mergi do main / Pouze ručně** — uložené zvlášť pro projekt a nástroj.

Globální automatika je zapnutá bez ručního kroku. Přepínač je v aplikaci
**Nastavení → Obecné** („Automatická aktualizace map po mergi do main“), platí
pro celou instanci a ukládá se v jejím datovém adresáři, nikdy per projekt.
Server ho mění přes `POST /api/map-refresh/configure {enabled}`. Při vypnuté
automatice worker nesleduje main, ale výslovné „Aktualizovat teď“ dál zpracuje.
Složky bez `refs/heads/main` nemají merge trigger; Graphify mohou používat ručně.

## Trigger

Worker kontroluje `refs/heads/main` každého projektu po 5 s, když právě
nedokončuje běh. Nová revize zařadí nástroje s volbou „Po mergi do main“.
Zachytí fast-forward, merge commit, squash a přímou změnu main; změny jiných
worktrees či rozepsané soubory ho nespustí. Proto funguje i když Git operace
aplikace bezpečnostně vypínají `core.hooksPath`. Žádný uživatelský Git hook se
nepřepisuje. Když je aplikace zavřená, změna main se zachytí po jejím spuštění.

Projekt bez stabilní sady (`graphify-out/graph.json` nebo
`archify-out/deliver-receipt.json`) dostane počáteční běh chybějícího nástroje,
pokud má nástroj volbu „Po mergi do main“. Selhaný běh se sám neopakuje; další
pokus je nový merge nebo „Aktualizovat teď“.

## Izolace a provedení

- Každý projekt se řeší přes jeho registraci a ověřený hlavní Git pracovní strom.
  Neexistuje žádný globální sloučený graf. Worktrees jednoho repozitáře používají
  mapu svého hlavního projektu.
- SQLite `map-refresh/state.sqlite` drží globální přepínač, poslední pozorovanou
  revizi, čekající revizi, vlastníka běhu, lease, režimy obou nástrojů, příznak
  výslovného požadavku a poslední výsledky.
- Claim se rozhoduje v `BEGIN IMMEDIATE`. Nejvýše jeden běh celé instance je
  aktivní; další mergnutí zpracuje následný běh z nejnovější pozorované revize.
- Snapshot čte pouze commit, nikoli dirty worktree: běžné UTF-8 textové soubory,
  bez symlinků/submodulů, `.env`, závislostí, vendoru, agentních instrukcí a bez
  `graphify-out/` i `archify-out/`. Limit snapshotu je 800 souborů / 8 MiB,
  soubor 1 MiB. Graphify navíc uplatní svůj limit 500 zdrojových souborů a
  `.graphifyignore`.
- Graphify používá původní `extract --code-only` + `cluster-only --no-label`.
- Archify: jedna session Claude Code Sonnet, nejvýše 10 tahů; průzkum má 6 tahů
  a při jejich vyčerpání následuje jeden rezervovaný dokončovací tah bez nástrojů.
  Společný limit je 600 sekund pro model a nativní kontroly. Model má Read/Glob/Grep, nikoli zápis nebo shell.
  Důkazy se kontrolují proti konkrétním řádkům snapshotu. Následují původní
  `validate`, `deliver`, `visual-check`, 9/9 showcase bez chyb/varování a browser pass.
  Je to jediné místo, kde aplikace spouští model.
- Agent ani renderer nepíše přímo do projektu. Před publikací se ověřuje projekt,
  aktuální main, owner a lease. Novější main zneplatní starý výsledek.
- Selhání extrakce/modelu/validace nic nepřepíše; zůstane poslední funkční sada.

## Výstupy

| Nástroj | Složka | Soubory |
|---|---|---|
| Graphify | `graphify-out/` | `graph.json`, `graph.html`, `GRAPH_REPORT.md`, `opora-receipt.json` |
| Archify | `archify-out/` | `map.architecture.html`, `map.architecture.json`, `deliver-receipt.json`, `visual-check-receipt.json`, `SPEC.md` |

Sada se publikuje až po úspěchu celého běhu nástroje; každý soubor jde přes
`<name>.tmp` a `os.replace`. V `graphify-out/` smí zůstat `cache/` a zámek
`opora-build.lock`; ostatní mezivýstupy (validate receipt, evidence, screenshoty)
zůstávají v dočasné složce. Ruční `POST /api/graphify/generate` zapisuje stejné
soubory stejným způsobem. Když projekt je git repo a složku neignoruje, aplikace
přidá řádek do lokálního `.git/info/exclude`; `.gitignore` projektu se nemění.

## API

- GET `/api/map-refresh/status?project=ID` — stav, režimy, revize a poslední běhy.
- GET `/api/map-refresh/config` — `{enabled}` globálního přepínače.
- POST `/api/map-refresh/configure` — `{enabled}` pro celou instanci.
- POST `/api/map-refresh/settings` — `{project,tool,automatic}`.
- POST `/api/map-refresh/retry?project=ID&tool=archify` — výslovný běh.

Všechny POST podléhají existující kontrole Host/Origin/JSON.
UI po změně dokončené revize načte nový artefakt. Volba uložená v jednom projektu
se nepřenáší do jiného ani z Graphify do Archify.
