# Noční směna 2026-10-14/15: Schránka řízená agenty

Zadání člověka: „pracuj do rána, vyvíjej navržený koncept, aby fungoval; úkoluj Hermese a ChatGPT, pouštěj hodně agentů a subagentů.“ Koncept: [docs/schranka-neurony.md](../schranka-neurony.md), [docs/zrcadlo.md](../zrcadlo.md).

## Cíl do rána

Jeden fragment Schránky v Ample projde celým cyklem 8 bran **jen přes booleovské ovládání agenta** (`/next` → návrh → potvrzení) a na plátně vznikne oblast → sektor → karty. Navrhovatel je jiný agent než potvrzovatel (Hermes navrhuje, Claude potvrzuje, ChatGPT kritizuje). Zrcadlo a Celeris jsou zapnuté a jejich výstup je vidět ve Schránce.

## Kusy

| Kus | Obsah | Stav |
|---|---|---|
| K1–K4, K9 | kontrakt, disciplíny, brány, plán, Celeris | hotovo (61ec336…579cda9, abd536a) |
| K5 | frontend disciplín, bran, poučení, povolení kontroly | běží |
| K8b | napojení Zrcadla + načtení `.env` ve spouštěči | běží |
| K10 | smazat backendové aliasy track/set-track/effectiveTrack | po K5 |
| K6 | skill: CLI cyklu pro agenta (`opora_cycle.py next/propose/gate`) + recept | po K5 |
| K11 | panel Zrcadla v Přehledu Schránky | po K8b |
| K12 | Hermes jako navrhovatel: role, zadání, napojení přes skill | po K6 |
| K7 | ukázka na Ample (záloha, dry-run, 1 fragment přes 8 bran) | po K6, K12 |
| K13 | závěrečné ověření, restart backendu, zpráva | konec |

## Pravidla směny

Kontrakt → subagent s přesným zadáním → kritik (ChatGPT `codex exec`, Hermes `hermes -z` jako druhý pohled) → ověření hlavním vláknem (`uv run pytest backend tools`, `npm test`, `npm run build`) → commit na `main` po kusech. Živá data jen se zálohou a po dry-runu. Nic se nepushuje. Klíče jen v `.env` (mimo git), nikdy v logu ani výstupu.

## Průběh

| Čas | Krok | Stav |
|---|---|---|
| noc | K5 UI jen zobrazení (7c45915), K6 CLI cyklu `opora_cycle.py` (e7ec9ec, podklad rolí od Hermese), K8b Zrcadlo + `.env` + pojistná verze před placed (f18ee69), K9 Celeris (abd536a), K10 reject-proposal a úklid aliasů (4e1f29d) | hotovo |
| noc | Rozhodnutí člověka: Schránka jen pro agenty, bez ovládání v UI; výzkumná smyčka v pískovišti (kontrakt §11, f2f2192) | zapsáno |
| noc | Prostředí: backend s Celeris (klíč z `.env`), služba Zrcadla 127.0.0.1:8750, pískoviště `cb1f8a93…` se 17 zadáními | běží |
| noc | Výzkum: 17 výzkumníků (Claude + web) – všech 17 disciplín verdikt feasible, 5–8 důkazů, kořeny na revizi 2 | hotovo |
| noc | Poznatek: souběžní agenti si přepisovali soubory ve sdíleném scratchpadu → pravidlo „vlastní složka na agenta“; `opora_read vault --discipline` doplněno (c32aa21) | opraveno |
| noc | Fáze bran: pilot BE (Hermes navrhuje, ChatGPT hodnotí ≥8/10, Claude potvrzuje) | běží |
