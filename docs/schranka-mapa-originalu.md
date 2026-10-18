# Neuronová síť Schránky vs. originály 00–09 (stav 2026-10-15)

Originály: `I:/1. Projekty/08_AGI/neuron-brain/00–09`. Přebíráme funkční principy, ne biologickou metaforu ani stack.
Modely Haiku, Sonet a Opus jsou v originálu role. Tady je hrají vnější agenti, protože aplikace model nespouští, viz `CLAUDE.md`.

Stav: ✅ hotovo · 🟡 částečně · ❌ chybí · ⛔ blokováno rozhodnutím.

| Princip originálu | V OPORA | Stav | Kde to vidíš v aplikaci | Co chybí |
|---|---|---|---|---|
| **Buňka**: uzel s cílem, vstupem, výstupem, pamětí a hranicí (00, 06) | fragment s `synthesized.checks` + jeho karta s GOAL (K15, `docs/schranka-bunka.md`) | 🟡 | Schránka → fragment → pruh bran; karta → kontroly | Rozpočet a úroveň dat v pokynu; disciplína je zatím štítek, ne vykonavatel |
| **Síť**: stav teče uzly (00, 06) | oblast → sektor → karty, vazby `next` | 🟡 | plátno, Velín | Typovaná předávka mezi disciplínami (be → fe) |
| **Impulz a rozsah** (05) | brána `scoped` | ✅ | pruh bran | – |
| **Dvě polarity** (02, 03) | brána `weighed {benefit, risk}` | ✅ | pruh bran | – |
| **Typovaný mikrokrok** TYP/CO/KDE/JAK/OVĚŘENÍ (04) | `synthesized {type, done, steps, layer, nonGoals, checks}` | 🟡 | detail fragmentu (kroky, vrstva, kontroly) | KDE (soubor), čas a náklad. OVĚŘENÍ je nově spustitelné (`checks`) |
| **Kontroly podle typu** (04) | – | ❌ | – | Pravidla podle typu mikrokroku, např. u RETRIEVAL nejdřív baseline |
| **Navrhuje jeden, rozhoduje jiný** (05) | `propose` / `yes` různými aktéry; u běhu vykonavatel ≠ ověřovatel | 🟡 ⛔ | historie bran (kdo navrhl, kdo potvrdil) | Ověřená identita aktéra (jméno je deklarované) |
| **Rozhodnutí ano / jinak / ne** (05) | brána `decided` | ✅ | pruh bran | – |
| **Změna směru se obhajuje** (05 „konstruktivní debata“) | **Duel** (K16): A proti B, grill, soudci, P(B > A), vítězný směr se uplatní | 🟡 | **Schránka → Směr → Duel** | Kalibrace P na skutečné výsledky; ≥ 2 nezávislí soudci |
| **Akce: agent dodá skutečný artefakt** (06, 07) | vykonavatel + `opora_cycle.py run-checks` (skutečný běh testů) | 🟡 | štítek „běh nahlášen – neatestováno“ u brány `verified` | Atestace běhu mimo vliv agenta |
| **Ověření proti acceptance, ne proti plánu** (07, 08) | `tests` pass/fail jen se záznamem skutečného běhu; „plán schválen“ ≠ „testy prošly“ (§13) | 🟡 ⛔ | brána `verified` (plán N/10 a testy zvlášť) | Atestace; baseline |
| **Baseline před optimalizací** (07) | – | ❌ | – | Měření výchozího stavu |
| **Paměť: funguje / nefunguje** (07) | `learned` s vyhasínáním; u buňky je druh poučení vázaný na výsledek běhu | 🟡 | Přehled → poučení disciplíny | Podmínka platnosti („nesedí za podmínek X“) |
| **Poučení mění chování** (05, 07) | poučení v `/next` a v `node-brief`; po duelu vzniká poučení | 🟡 | fronta agenta, poučení disciplíny | Povinná kontrola nového návrhu proti živým antipatternům |
| **Mez smyčky** (05, 08) | 3 kola na fragment; duel nejvýš 4 otázky na stranu | ✅ | „kolo N/3“, „vyčerpáno – čeká na člověka“ | – |
| **DNA projektu**: cíl, rozpočet, tabu (08) | **Představa** + trend „přibližujeme se / oddalujeme se“ (K16) | 🟡 | Duel → Představa a trend | Rozpočet, tabu a klíčové cesty; prior šumu trendu |
| **Trace každého kroku** (00) | append-only revize, návrhy, poučení, Zrcadlo | 🟡 | Historie, Revize | Čas a náklad kroku |

## Co je doložené testem

- **K15 (buňka):** e2e `test_opora_cell.py` běží nad skutečným serverem a skutečným pytestem: zadání → rozhodnutí → artefakt → `fail` → antipattern → nové kolo → `pass` → pattern. Podvržený test vykonavatele neprojde.
- **K16 (duel):** e2e `test_opora_duel.py` prochází přijetím změny, ponecháním A, syntézou, poučeními a trendem. Duplicitní argument P nezvýší.

## Otevřené rozhodnutí (⛔)

- **Ověřená identita aktéra a atestace běhu:** viz `docs/schranka-overovatel-navrh.md`.
- **Kalibrace P duelu na skutečné výsledky:** chybí oracle.
- **Rozpor „sektor = disciplína“ vs. „sektor = dodavatelný celek“:** lokální mapování OPORA. Originály ho nepředepisují.
