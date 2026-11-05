# Plátno 4 – monitoring (kontrakt)

Čtvrté ze čtyř pláten (`2026-11-03-novy-zaklad.md`). Řeší jednu věc: **výpadek nebo anomálie živého provozu se dostane k srdci jako chyba plátna, ne jako zpráva, kterou si někdo všimne za dvě hodiny.**

## Rozhodnutí
- Plátno 4 se staví, i když `docs/architektura-pro-agenty.md` (ř. 396, 473) říká „monitor procesů se nestaví“. To rozhodnutí je tímto zrušeno: dřívější monitor byl samostatná obrazovka, tohle je vstup do smyčky srdce.
- Žádný nový přenos. Cesta k srdci už existuje: `log_canvas(canvas=4, kind="….failed")` → outbox `canvas.failed` → vstup `canvasFailed` → srdce se probudí (okno 20 s). Plátno 4 jen dodá události, které tam dnes nikdo neposílá.
- Jedno rozhraní pro všechny projekty: sondy se berou z grafu projektu (hosty jako `web-status`), druh projektu se nečte.

## Vrstvy (jako Studio)
1. **Skutečnost**: sondy měří hosty projektu a zapisují výsledek.
2. **Simulace**: případy výpadku (`crash|slow|restore`) nad modelem Studia. Je to model, ne měření; stejné případy jako `env`/`expect` plátna procesů.

## Milníky (jen aktuální, po každém stop)
- **M1 detektor (backend)**: `backend/agi_pletor/monitoring/`: `probes.py` (HTTP sonda hostu: stav, latence), `detector.py` (čistá funkce: řada výsledků + práh → `ok|slow|down`), `monitor.py` (tik: změří, porovná s posledním stavem, zapíše **jen přechod**). Přechod `ok→down` píše `outage.failed`, `ok→slow` píše `slow.failed`, návrat `outage.recovered` (bez `.failed`, srdce se neprobouzí). Stav po hostu v DB projektu; stejná chyba se nezapíše podruhé, dokud se host nevrátí. Prahy: `down` = 3 selhání po sobě, `slow` = latence nad prahem 3 měření po sobě; v nastavení projektu, výchozí rozumné. Test u každého modulu.
- **M2 prostoje plátna 1**: `stalls.list_stalls` se pravidelně volá a prostoj plátna 1 se zapíše do logu.
- **M3 plátno (frontend)**: `frontend/project/monitoring-canvas/`: hosty jako uzly se stavem, historie přechodů, lišta Skutečnost / Simulace, na sdíleném `shared/flow-editor`.
- **M4 simulace**: případy výpadku nad Studiem, srovnání se Skutečností.
- **M5 CI**: sonda `ci` (stav posledního běhu) až bude CI v Ample; dnes v repu nic není.

## Mimo rozsah
Notifikační kanály mimo srdce (e-mail, push): srdce rozhodne, komu co řekne. Sběr metrik do časových řad, dashboardy zátěže.

## Ověření
`uv run pytest backend/agi_pletor/monitoring`, `npm test`, `npm run build`. Měřítko hotovo celku: shozený host na pískovišti → do 2 minut `canvas.failed` v outboxu → srdce vydá ticket; po návratu hostu `outage.recovered` a žádný další budíček.
