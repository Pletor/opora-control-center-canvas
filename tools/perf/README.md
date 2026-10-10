Měřicí skripty výkonu plátna (sektor Výkon a škálování). Měří se jen na kopii dat, nikdy na `.data/production`; `perf_common.copy_dir` živá data odmítne.

- `data_copy.py [zdroj] [cíl]` vyrobí kopii z `.data/production` do `.data/perf-copy` (v .gitignore); SQLite přes backup API, zdroj jen pro čtení.
- `bench_gets.py <kopie> [--repeat N]` latence čtecích endpointů UI, druhý běh je teplý; s `--repeat` > 2 i p50/p95/p99 teplých běhů a u endpointů s ETagem čas podmíněného dotazu (304).
- `bench_contention.py <kopie> <okna>` souběh: okna pollují výpis verzí jako dřívější `setInterval` 3 s bez guardu, mezitím leases a node-brief.
- `bench_projects.py <kopie> [--other P]` souběh projektů (karta P2): smyčky výpisu verzí a node-brief na Ample, mezitím leases a frontier na Ample i druhém projektu (medián, p95, max proti klidu).
- `bench_vsave.py <kopie>` a `bench_writes.py <kopie>` zapisují do kopie (verze, rozhodnutí, pipeline); `bench_writes` vypíše i délku odpovědi zápisu (cíl karty P3 < 10 kB).
- Výstup jde vždy v UTF-8 (`perf_common`), na Windows konzoli netřeba `PYTHONIOENCODING`.

Výchozí projekt a karta jsou z Ample (`--project`, `--node`, `--workspace` je změní). Spouštěj z kořene repa: `uv run python tools/perf/<skript>.py <kopie>`.
