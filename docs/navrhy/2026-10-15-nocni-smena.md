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
