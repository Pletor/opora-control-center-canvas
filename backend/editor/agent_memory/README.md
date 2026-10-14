Paměť projektu pro agenty: nastavení, pravidla must/must_not, připnutá rozhodnutí, fáze uzlu, porty bloků, uzavření karty a zprávy na vazbách (desktop_v3_state.py, revizovaný stav s CAS).

`agent-output.output.usage` volitelně nese `tokens`, `durationMs`, `attempts`: nezáporná celá
čísla za tento výstup, nikoli kumulativní stav celé relace. Neznámé hodnoty vynech nebo pošli
`null`; měřená nula je platná. Údaje jsou hlášené agentem a uchované v historii výsledků.
`GET /api/desktop-v3/usage-summary?project=P&workspace=W` vrací součty za karty a rekurzivně
za sektory. Chybějící údaj v některém výstupu znamená nedostupný součet, ne nulu. Historie
se nesmí sčítat jen z první stránky. `node-brief.usage` obsahuje vlastní součet a součet
sektoru, je-li cílem sektor. Peněžní cenu aplikace z tokenů neodhaduje.
Výstup modelu opora.agent-output/1: stav bloků, zprávy na vazbách, návrh uzavření karty a rozhodnutí zapsané s by "agent" pod CAS revizí (agent_output.py).
Adresný přístup k jednomu bloku karty: čtení bloku s dětmi/rodičem a zápis add/update/remove/todo s přečíslováním pod CAS revizí (block_access.py).
Pracovní prostor agenta u karty: pět sekcí (rámec, postup, chyby, opravy, předávka) revizovaných jako text uzlu, částečný zápis pod CAS, smazání s kartou a souhrn vyplněnosti všech karet jedním dotazem (agent_workspace.py).
Samostatná pravidla a rozhodnutí: `memory_items.py` poskytuje adresné add/update/remove přes
`/api/desktop-v3/rule` a `/api/desktop-v3/decision`. `expected` je původní položka (null při
přidání); porovnání a zápis drží graph_lock. Nová revize celého stavu vzniká vždy, ale klient
neposílá zbytek stavu a nezahodí změny jiných položek. Validaci obsahu provádí DesktopV3State.
Odpověď je štíhlá (karta P3): `{revision, readOnly, item}`, u `/pipeline` `{revision, readOnly, nodeId, stages}`;
`?full=1` přidá celý stav. Zápis staví na mělké kopii uloženého stavu a `save(base=...)` znovu
neověřuje uzly, které se nezměnily (totožné objekty). `DesktopV3State.current` drží stav v cache
podle tokenu dat a revize (`backend/canvas/read_cache.py`); vrácený stav je jen ke čtení.
Návrh pravidla od agenta (`by: "agent"`, karta, projekt i cesta) posoudí člověk přes
`/api/desktop-v3/rule-review` `{project, workspace, id, decision: approve|reject, expected}`:
schválení uloží pravidlo bez `by` (od té doby platí v `node-brief`), zamítnutí ho odebere.
Smí jen člověk (cookie `opora_ui`; agent 403, neznámý 428); `expected` je přečtený návrh (CAS).

`port_spawn.py` vytváří následníka z `port.onMet` při přechodu bloku do `met` ve společném
ukládání stavu (UI, adresný blok i agent-output). Zamítnutý port přeskočí. Tabulka
`port_spawns` drží jedinečnou kombinaci workspace/karta/blok/port i po restartu a smazání
následníka. Šablona má název, účel, zadání, text a volitelné kontroly; nic nespouští.
Nová karta leží vpravo za sourozenci, aby výška rozbaleného obsahu nevedla k překryvu.
Odpověď s `graphChanged` upozorní UI na nutnost znovu načíst graf.
