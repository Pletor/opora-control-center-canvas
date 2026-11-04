# Monitoring (plátno 4)

Měří hosty projektu a výpadek nebo zpomalení pošle srdci jako chybu plátna 4. Kontrakt: `docs/navrhy/2026-11-04-platno-monitoringu.md` (milník M1).

- `probes.py`: jedno měření hostu `{ok, status, latency_ms, error}` přes klienta stavu webu (`integrations/web_probe_client.py`: HTTPS, timeout 5 s, privátní adresy odmítne). `ok` je jen stav `up`. Transport je parametr, testy nesahají na síť.
- `detector.py`: čistá funkce `detect(results, slow_ms=2000, streak=3)` → `ok|slow|down`. `down` = 3 neúspěšná měření po sobě, `slow` = 3 úspěšná měření po sobě nad prahem latence.
- `monitor.py`: tik projektu. Hosty bere jako `web-status` (`collect_hosts` nad přijatým grafem, nejvýš 20). Stav po hostu (`state` + poslední 3 měření) drží `<data>/projects/<id>/brain/monitor_state.json`. Do logu pláten (`flow/canvas_log.log_canvas`, plátno 4, autor `monitor`) zapíše jen přechod:
  - do `down`: `outage.failed`;
  - do `slow`: `slow.failed`;
  - zpět do `ok`: `outage.recovered`. Nekončí `.failed`, srdce se neprobouzí.

  Stejný stav se podruhé nezapíše, dokud se host nevrátí.

## Zapnutí

Smyčka startuje s aplikací (`app/factory.py`, lifespan) a tiká každých 60 s. Měří jen projekty, které mají v `project.json` nastavení zapnuté (výchozí je vypnuto, `draft` se neměří):

```json
"settings": {"monitor": {"enabled": true, "slowMs": 2000}}
```

`slowMs` je nepovinný práh latence v ms.

Ověření: `uv run pytest backend/monitoring`.
