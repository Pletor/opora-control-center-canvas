# Strážci

Tichý dohled bez modelu, kontrakt `docs/strazci.md`. Strážci jen čtou a hlásí; nikdy nemění zadání, kroky ani
obsah karet.

- `registry.py` – `Guard {id, label, every_s, run(ctx)}`, `GuardContext` a první sada (`mapa`, `prace`, `cesty`, `pravda`, `zkusenost`, `trend`).
- `manager.py` – `GuardianManager`: daemon vlákno (tick `OPORA_GUARDS_SECONDS`, výchozí 30 s, vypnutí
  `OPORA_GUARDS_WORKER=0`), start a stop v lifespan `backend/app/factory.py`. Výjimka strážce skončí v jeho
  `lastError`, worker i ostatní strážci běží dál. Stav (`lastRunAt`, `lastOkAt`, `lastError`) je jen v paměti.
- `findings.py` – ověření výstupu strážce a diff s tabulkou `guard_findings`: nový → `guard.alert`, trvající →
  `last_seen`, zmizelý → `resolved_at` a `guard.resolved`; vyřešené starší 14 dní se mažou. První běh strážce
  v projektu a dávka víc než 20 nových nálezů vydají jednu souhrnnou `guard.alert` (`rule: baseline` / `batch`).
- `guard_mapa.py` – kontrola mapy (`map_check`) nad přijatou architekturou, jen při změně hlavy (otisk grafu
  a poslední doklad cesty).
- `guard_prace.py` – nároky a běhy: `work.lease-expired`, `work.no-heartbeat` (>10 min), `work.step-stalled` (>30 min).
- `guard_cesty.py` (120 s) – `lastRun` cest: `journey.stale`, `journey.failed`, `journey.blocks-card` (karta čeká na
  uzavření a brání jí brána cest, stejný výpočet jako `opora_card_done.journeys_by_card`).
- `guard_pravda.py` (300 s) – `truth.worktree-behind` (větev worktree > 20 commitů za hlavní větví, jen lokální Git,
  timeout 10 s) a `truth.proposal-stale` (návrh čeká na člověka > 24 h).

- `guard_zkusenost.py` (10 s, při události) – od kurzoru dočte `card.closed`, `merge.done` a doklady cest, záznam
  (`zkusenost_record.py`, čisté funkce) zařadí do outboxu `guard_experience` a doručí ho do OpenVikingu klíčem role
  jako `backend/library/harness_memory.py` (claim/lease, retry, `waiting-role`). Nálezy nevydává.
- `guard_trend.py` (900 s) – vzorek osmi čísel do `guard_trend` (díry mapy z `mapGaps`, cesty, karty, zaseknutá
  práce, návrhy čekající na člověka), retence 90 dní. Nálezy nevydává.

Nálezy mimo strážce `mapa` čtou agenti v agent-state `guards` / `cards[].guardFindings` a v node-brief `guards`
(`backend/canvas/opora_agent_state_guards.py`); díry mapy jen v `mapGaps` a `holes`.

Rozhraní: `GET /api/strazci?project=`, `GET /api/strazci/findings?project=&node=&open=1`,
`GET /api/strazci/trend?project=&metric=&days=`
(`backend/api/editor/strazci_routes.py`). `opora.local.toml` sekce `[strazci]` (`enabled`, `seconds`) se převádí na
proměnné prostředí v `tools/opora.py`. Testy s falešným časem leží vedle modulů (`test_<modul>.py`).
