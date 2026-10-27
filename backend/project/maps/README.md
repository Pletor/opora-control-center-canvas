Mapy projektu podle `docs/mapy-projektu.md`: Graphify runtime a worker (bez modelu), fronta obnovy (`map_refresh`, `state.sqlite`, automatika zapnutá bez ručního kroku), snapshot commitu main a publikace jedné stabilní sady na místě.

- `map_artifacts.py` — pevné cesty (`graphify-out/`), seznam publikovaných souborů, `missing_tools()` pro počáteční běh a `publish()` s atomickým zápisem `<name>.tmp` + `os.replace`; zámek, kontrola odkazů/junctionů a limity velikosti.
- `map_git_exclude.py` — složku map, kterou git projektu neignoruje, přidá do lokálního `.git/info/exclude`; `.gitignore` projektu nemění.
- `map_refresh.py` — fronta: sledování `refs/heads/main`, počáteční běh chybějící sady, „Aktualizovat teď“ i při vypnuté automatice, jeden běh na instanci, lease a ochrana proti staré revizi. Testy nastavují `OPORA_MAP_REFRESH_WORKER=0` (`backend/conftest.py`), aby worker nevznikl.
- `map_refresh_pipeline.py`, `map_refresh_snapshot.py`, `graphify_runtime.py`, `graphify_worker.py` — sestavení v dočasné složce a volání původních nástrojů.
