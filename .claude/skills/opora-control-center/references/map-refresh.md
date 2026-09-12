# Aktualizace projektových map

Oba prohlížeče používají jedinou komponentu `MapUpdateMenu`:
- **Aktualizovat teď** — Graphify přímo lokálně, Archify zařadí Sonnet běh.
- **Načíst uložený výstup** — pouze GET, žádný model.
- **Po mergi do main / Pouze ručně** — uložené zvlášť pro projekt a nástroj.

Globální povolení automatizace je trvalé v datovém adresáři instance, nikoli v
prohlížeči. Explicitní operátorský POST `/api/map-refresh/configure` s
`{"enabled":true}` zapíná worker; nový testovací datový adresář je vždy vypnutý.
Aktuální projekty se při prvním zapnutí pouze zaregistrují. Nově připojený Git
projekt potom dostane počáteční generování. Složky bez `refs/heads/main` nemají
merge trigger; Graphify mohou používat ručně.

## Trigger

Worker kontroluje `refs/heads/main` po 5 s, když právě nedokončuje běh.
Zachytí fast-forward, merge commit, squash a přímou změnu main; změny jiných
worktrees či rozepsané soubory ho nespustí. Proto funguje i když Git operace
aplikace bezpečnostně vypínají `core.hooksPath`. Žádný uživatelský Git hook se
nepřepisuje. Když je aplikace zavřená, změna main se zachytí po jejím spuštění.

## Izolace a provedení

- Každý projekt se řeší přes jeho registraci a ověřený hlavní Git pracovní strom.
  Neexistuje žádný globální sloučený graf. Worktrees jednoho repozitáře používají
  mapu svého hlavního projektu.
- SQLite `map-refresh/state.sqlite` drží poslední pozorovanou revizi, čekající
  revizi, vlastníka běhu, lease, režimy obou nástrojů a poslední výsledky.
- Claim se rozhoduje v `BEGIN IMMEDIATE`. Nejvýše jeden automatický běh celé
  instance/úložiště je aktivní; tedy nejvýše jeden na projekt. Další mergnutí
  zpracuje následný běh z nejnovější pozorované revize.
- Snapshot čte pouze commit, nikoli dirty worktree: běžné UTF-8 textové soubory,
  bez symlinků/submodulů, `.env`, závislostí, vendoru a agentních instrukcí.
  Limit snapshotu je 800 souborů / 8 MiB, soubor 1 MiB. Graphify navíc uplatní
  svůj limit 500 zdrojových souborů a `.graphifyignore`.
- Graphify používá původní `extract --code-only` + `cluster-only --no-label`.
- Archify: jeden Claude Code Sonnet, nejvýše 10 tahů, společný limit 600 sekund
  pro model a nativní kontroly. Model má Read/Glob/Grep, nikoli zápis nebo shell.
  Důkazy se kontrolují proti konkrétním řádkům snapshotu. Následují původní
  `validate`, `deliver`, `visual-check`, 9/9 showcase bez chyb/varování a browser pass.
- Agent ani renderer nepíše přímo do projektu. Před publikací se ověřuje projekt,
  aktuální main, owner a lease. Novější main zneplatní starý výsledek.
- Selhání extrakce/modelu/validace zachová poslední funkční mapy. Neprobíhá žádný
  nekonečný placený retry; další merge nebo explicitní aktualizace je nový pokus.

## Výstupy

Původní bytes HTML/JSON se ukládají u projektu do
`.opora-map-refresh/versions/<id>/`. Atomický `current.json` vybírá aktuální
verzi každého nástroje. Uchovávají se aktivní verze a tři nejnovější archivy.
Graphify zachovává také standardní `graphify-out/graph.json` pro CLI agenty.
Archify automatika nepřepisuje Git-tracked historické exporty v
`docs/architecture/archify`; viewer načte vybranou novou verzi. Ručně změněné
potvrzení původního exportu přepne čtečku zpět na ruční výstup.

## API

- GET `/api/map-refresh/status?project=ID` — stav, režimy, revize a poslední běhy.
- POST `/api/map-refresh/settings` — `{project,tool,automatic}`.
- POST `/api/map-refresh/retry?project=ID&tool=archify` — explicitní běh.
- POST `/api/map-refresh/configure` — `{enabled}` pro celou instanci.

Všechny POST podléhají existující kontrole Host/Origin/JSON.
UI po změně dokončené revize načte nový artefakt. Volba uložená v jednom projektu
se nepřenáší do jiného ani z Graphify do Archify.
