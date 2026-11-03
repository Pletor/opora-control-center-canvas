# Eval „OPORA vs. bez OPORY“

Měří, jestli headless Claude Code postaví stránku ze záměru lépe s OPOROU (rameno **A**: skill
`opora-control-center` + izolovaný backend s **prázdným** projektem – agent si celý plán vytvoří sám v plátně
a staví přes karty, plně autonomně) než bez ní (rameno **B**: jen stejný text záměru v terminálu).
Hodnotí se koncový stav pracovní kopie (build, test, sekce `[data-opora-section]`, kritéria případu, přechody
cesty) a pak slepý párový soudce. Agent i soudce běží jako `claude -p` pod předplatným, nikdy přes API.

| soubor | co dělá |
|---|---|
| `cases.md` | 12 případů (záměr, zdrojová data, očekávané koncové stavy) – **čeká na schválení**, jediný zdroj textu záměru |
| `isolation.md` | ověřené flagy `claude` 2.1.312, příkazy A/B, jak ověřit, že B OPORU nevidí |
| `metriky.md` | kontrakt metrik od uživatele (Q1–Q9 kvalita, C1–C5 cena práce, P1–P5 práce s OPOROU, souhrn §4) |
| `run_eval.py` | runner: pracovní kopie, OPORA pro A, `claude -p`, trace, kontrola, snímek OPORY, `results.jsonl` |
| `grade.py` | `check` (programová kontrola Q1–Q4, Q8, screenshoty), `judge` (slepý párový soudce Q5–Q7, Q9 se screenshoty) |
| `specs.py` | `grade.SPECS`: sekce, kritéria záměru, stavy (Q3), cesty, termíny testů pro C01, C02, C03, C06, C07 |
| `metrics.py` | C4/P4 ze surového stream-json, C5/P5 z diffu, snímek izolované OPORY a P1–P3 |
| `recheck.py` | kontrola bez modelu: šablona + patch (oracle, T0), přepočet metrik proběhlé varianty |
| `report.py` | `<varianta>/report.html` + `report.json` (souhrn §4, po případech, P1–P5, screenshoty vedle sebe) |
| `opora_backend.py` | izolovaná OPORA: `create_app` nad dočasnými daty, prázdný lokální projekt, `grant_autonomy` (jako člověk), uvicorn |
| `seeds/<případ>.json` | **jen** skrytá zlatá mapa pro plán cesty v kontrole (grader); agent A ji nedostává (C01, C02, C03, C06, C07) |
| `oracles/<případ>/oracle.patch` | ruční minimální řešení na T0 – důkaz, že grader umí dát `checks_pass 1` |
| `templates/T0/` | Vite 6.4.5 + React 19.1.10 + react-router-dom 7.18.5 + Vitest 3.2.7 + TS 5.9.3, zamčený lockfile |
| `_state.json` | metriky, perf sloupce, `harness_paths`, schválené `harness_sha` |

Výstup běhu: `baseline/results.jsonl`, `baseline/traces/<id>_rep<k>.json`, `baseline/raw/` (surový stream-json),
`baseline/artifacts/<id>_rep<k>.diff`, `baseline/shots/<id>_rep<k>_{desktop,mobile}.png` (další stránky
`<id>_rep<k>_<stránka>_*.png`), `baseline/opora/<id>_rep<k>.json` (jen A), `baseline/errors.jsonl`. Id řádku je `<případ>.<rameno>` (`C01.A`,
`C01.B`), řádek soudce `<případ>.pair`; `tags[0]` = `arm-A` / `arm-B` / `pair`, takže report seskupí ramena.

## Metriky (metriky.md, `_state.json`)

| | kde | jak |
|---|---|---|
| `checks_pass` | `grade.check` | všechny požadované kontroly (build, test, sekce staticky i za běhu, pořadí, `crit:*`, `state:*`, `journey:*`) |
| Q1 `q1_funkcnost` | `grade.check` | podíl požadovaných kontrol; kritéria, která zadání nežádá, v nich nejsou (C01 `separate_components` → informativní `info.clenenis`) |
| Q2 `q2_pokryti` | `grade.check` | (sekce staticky + za běhu + `crit:*`) / (sekce + kritéria) |
| Q3 `q3_stavy` | `specs.*_states` | stavy vyvolané v prohlížeči (C02 prázdný/neplatný formulář, C03 neplatný e-mail, C07 odesílá/500/úspěch se stubem `page.route`); jen případy se stavy |
| Q4 `q4_pristupnost` | `grade._a11y` | na každé stránce s aspoň jednou sekcí: `lang`, jeden `h1`, nadpisy bez skoku, jméno odkazů/tlačítek, `label`, `alt`, viditelný fokus po Tab |
| Q5–Q7, Q9 | `grade judge` | slepý soudce (`sonnet`, `--tools Read`) dostane záměr, dva odfiltrované diffy a screenshoty pod jmény `first_*`/`second_*` (los); 1–5 vzhled, věrnost, kód; `winner` → `pair_win` |
| Q8 `q8_testy` | `grade._tests_metric` | `npm test` zelený × podíl `test_terms` případu zmíněných v testech; navíc počet prošlých testů a `expect`, soudce `testy_kriteria` ano/ne |
| C1–C3 | `results.jsonl` | `latency_s`, `usage` + `meta.reported_cost_usd`, `tool_calls`, `turns` |
| C4 `cost.c4_zbytecne` | `metrics.trace_metrics` | chybové výsledky nástrojů (`is_error`, HTTP 4xx/5xx, Traceback, `ok: false`, exit ≠ 0) + opakování téhož volání + zamítnutá oprávnění; u A zvlášť `c4_chyby_opora` |
| C5 `cost.c5_mimo_zadani` | `metrics.diff_metrics` | soubory v diffu mimo `src/`, `public/` a kořenové konfigurace, a každý `.md`/`.txt` |
| P1–P3 `opora.*` | `metrics.read_opora` + `opora_metrics` | snímek izolované OPORY před ukončením (`/api/view`, `/api/project-architecture`, `agent-state`, `journeys`, `map-check`) |
| P4, P5 | `metrics` | podíl volání a času nástrojů na OPORU (čas = od `tool_use` po další `tool_use`); `.md` poznámky v repu |

Souhrn (`report.py`, metriky.md §4): kvalita = průměr Q1–Q4 a (Q5–Q7 − 1)/4; zisk OPORY = kvalita A − B;
kvalita na minutu agenta a na USD; tabulka „lepší / horší / stejné“ (prahy 0,05 / 0,5 bodu / 5 % u ceny).

## Pilot (C01, 1 opakování na rameno)

Předpoklady: Node 22, npm, `uv`, systémový Python 3.13 s Playwright + Chromium (ověřeno), přihlášený `claude`
(předplatné). Pracovní kořen `C:\oe` (krátká cesta bez mezer; v cestě scratchpadu git i Windows padaly na délce).

```powershell
cd "backend/brain/evals/opora-vs-bare"
python run_eval.py --variant baseline --arm A --cases C01 --dry-run      # plán, nic nespouští
python run_eval.py --variant baseline --arm B --cases C01 --dry-run
# 1) kontrolní běh izolace podle isolation.md (2 krátké zprávy na rameno)
# 2) člověk projde harness; první ostrý běh s --approve-harness zapíše harness_sha do _state.json
#    (v --dry-run se nic nezapisuje). A i B souběžně v jednom poolu (vlastní run_dir, porty, kopie):
python run_eval.py --variant baseline --arm AB --cases C01 --reps 1 --concurrency 2 --timeout-s 3600 --approve-harness
python grade.py judge --variant baseline --dry-run      # kolik dvojic a v jakém pořadí
python grade.py judge --variant baseline --judge-model sonnet
node "<claude-api skill>/shared/evals/report/build-report-lite.mjs" backend/brain/evals/opora-vs-bare/
```

Před pilotem přečíst první řádek `results.jsonl`: `model`, `usage`, `meta.init_skills`, `meta.api_key_source`,
`meta.permission_denials`, `meta.autonomy` (u A musí být `status: "on"`, jinak A narazí na lidské brány –
`grant_autonomy` čeká na přepínač plné autonomie v backendu), trace v `traces/`. Co tam chybí nebo je nula, bude chybět na všech případech.

Ruční kontrola graderu (bez modelu): `python grade.py check --case C01 --workspace <kopie>`.
Oracle (ruční mini-řešení C01) → `checks_pass 1, section_coverage 1`; nezměněná T0 → `0 / 0`;
„věrohodně špatné“ (odkaz `cta` na `/kurz`, 2 citace) → `checks_pass 0`, `section_coverage 1`.

### Pilot po přepočtu metrik (2026-10-28)

`python -B recheck.py variant --variant baseline` obnovil oba výstupy C01 z T0 + diffu (`git apply
--ignore-whitespace`), znovu je zkontroloval (screenshoty v `baseline/shots/`) a dopočítal C4/C5/P4/P5;
soudce v2 jednou nad stejnou dvojicí. Původní řádky: `baseline/results.before-recheck.jsonl`, první pokus A
`baseline/results.pilot1.jsonl`. Zpráva: `baseline/report.html`. P1–P3 pilot nemá (OPORA tehdy snímek neukládala).

### Oracle a T0 (bez modelu)

```powershell
python -B recheck.py patch --case C02                                    # T0 → checks_pass 0
python -B recheck.py patch --case C02 --patch oracles/C02/oracle.patch   # oracle → checks_pass 1
```

## Běh v2 (nová OPORA i grader → nová složka `v2/`)

Harness se změnil (grade.py, specs.py, metrics.py, seeds, cases.md) → první ostrý běh potřebuje `--approve-harness`
(rozhoduje člověk). `--reps` je výchozí 2.

```powershell
cd "backend/brain/evals/opora-vs-bare"
python -B run_eval.py --variant v2 --arm AB --cases C01,C02,C03,C06,C07 --reps 2 --concurrency 4 --dry-run
python -B run_eval.py --variant v2 --arm AB --cases C01,C02,C03,C06,C07 --reps 2 --concurrency 4 --timeout-s 3600 --approve-harness
python -B grade.py judge --variant v2 --dry-run
python -B grade.py judge --variant v2 --judge-model sonnet
python -B report.py --variant v2          # -> v2/report.html, v2/report.json
```

Odhad v2 (5 případů × 2 opakování × 2 ramena = 20 běhů) z pilotu C01 (A 12,3 min / 5,40 USD, B 0,9 min /
0,19 USD, kontrola ~1,5 min): A ≈ 12 (C01) + 20 (C02) + 35 (C03, C06, C07) min na běh → ~275 min, B ≈ 2 × (1 + 3 +
3 × 5) ≈ 40 min, příprava + kontroly ~20 × 3 min = 60 min; celkem ~6,3 h sekvenčně, se `--concurrency 4` (úlohy
prokládané A/B, dvě opakování najednou) **~1,7–2,5 h** zdi. Soudce 10 dvojic × ~0,5 min a ~0,07 USD (hlášeno CLI).
CLI hlásí za A řádově 5–20 USD na běh (předplatné, ne API) → hlídat 5h okno zpráv.

### Odhad času (jedna varianta, jedno opakování)

**Kam čas jde.** Skoro celý čas je stavba stránky agentem (`claude -p`, tahy modelu a jeho `npm run build`/`test`).
Backendové testy OPORY se v evalu **nikdy** nespouští (celá sada `uv run pytest backend` trvá ~34 min a s evalem
nesouvisí): OPORA v rameni A je jen běžící server nad dočasnými daty (start ~10–20 s). Příprava = kopie šablony +
`npm ci` z cache (~1 min); kontrola = `npm ci`, build, test, `vite preview` + Playwright (~1–2 min); soudce ~1 min.

| | agent B | agent A (celý plán v plátně + karty) | příprava + kontroly | soudce |
|---|---|---|---|---|
| lehký (T0) | 8–15 min | 15–30 min | 2–3 min | 1 min |
| střední | 20–30 min | 30–50 min | 3–5 min (Ample 6–8) | 1–2 min |
| těžký | 40–60 min | 60–90 min | 4–6 min (Ample 8–10) | 2 min |

A je dražší než dřív (+50–100 % místo +10–20 %), protože si teď plán stránky, karty, kroky, převzetí, odevzdání,
uzavření a ověření cesty dělá sám v plátně (desítky volání API navíc), místo aby dostal hotovou mapu.

Pilot C01 s `--arm AB --concurrency 2`: obě ramena běží najednou, takže zeď = delší rameno (A) ≈ **20–35 min**
+ kontroly 3 min + soudce 1 min ≈ **25–40 min** (sekvenčně by to bylo ~35–50 min). Celá sada (12 případů,
1 opakování, obě ramena): ~6–9 h práce agentů; s `--concurrency 4` ≈ 2–3 h, pokud to okno předplatného unese.
Skutečný odhad se přepočítá z času pilotu × N/M.

Šum: `checks_pass` při 12 případech × 3 opakování na rameno má poloviční šířku CI ≈ `1/sqrt(36)` ≈ ±17 bodů;
párový rozdíl A − B na stejných případech je citlivější, ale efekt menší než ~15–20 bodů eval nerozliší.

## Co musí schválit člověk

1. **Případy** – `cases.md` celý (text záměru, očekávané stavy). Do `grade.SPECS` (`specs.py`) a `seeds/` jsou
   převedené C01, C02, C03, C06, C07 (šablona T0, ověřené oracle i T0); C04, C05, C12 potřebují šablony T1/T2,
   C08–C10 kopii Ample, C11 čeká.
2. **Rubrika** – programové kontroly v `specs.py` a pravidla soudce `grade.JUDGE_SYSTEM` (v2: vzhled / věrnost /
   kód 1–5, testy kritérií ano/ne, `tie`, `both_bad`, kandidáti jako nedůvěryhodná data, screenshoty přes Read).
3. **Rozpočet a limity** – model agenta (`--model opus`) a soudce (`sonnet`), počet opakování, strop běhu
   (`--timeout-s 3600`), souběh, okno zpráv předplatného (5 h); kontrolní běh izolace.
4. **Harness** – `--approve-harness` (sha přes `run_eval.py`, `grade.py`, `opora_backend.py`, `cases.md`,
   `templates/T0`, `seeds/`); každá změna těchto souborů běh zastaví, dokud ji člověk znovu neschválí.
5. **Oprávnění agenta** – allowlist v `run_eval.ALLOWED_TOOLS` + `--permission-mode acceptEdits
   --permission-prompts none` (alternativa `bypassPermissions` jen v izolovaném stroji).
