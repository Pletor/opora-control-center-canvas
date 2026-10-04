# Live Run: telemetrie sessions

Live Run jen **sleduje** externí sessions (Hermes, Claude lane) navázané na uzel. Aplikace z něj žádný model nespouští ani nezastavuje; vazbu session na uzel zakládá `POST /api/node-sessions/bind`, který asistent nemá (není v `opora_write.py`).

## Čtení

```bash
python "<SKILL_DIR>/scripts/opora_read.py" sessions --project <projectId> --workspace <workspace> --node NODE_ID --raw
```

- Bez `--node` vypíše celý workspace. Nejvýš 100 vazeb, příznak `truncated`.
- Stav je v poli `status`: `running` = ověřený proces, `recent_activity` = nedávná uložená událost, `idle`, `unknown` (zdroj nedostupný, důvod v `statusReason`, `sourceAvailable: false`). Souhrn bez `--raw` pole `status` nevypisuje, proto `--raw`.
- Dál `source`, `sessionId`, `parentSessionId`, `role`, `title`, `model`, `lastActivityAt`, `boundAt`, `events`, `metrics`.

## Co nelze tvrdit

- Nedostupný jeden zdroj neznamená selhání ostatních. Zachované položky mohou být staré.
- Otevřená konverzace ani vazba na uzel není důkaz běžícího modelu.
- Chybějící tokeny, USD či využití kontextu nejsou nula. Žádná vymyšlená procenta.

Tickety a jejich čtení: [external-agent.md](external-agent.md).
