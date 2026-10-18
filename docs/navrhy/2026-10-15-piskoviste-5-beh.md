# Pískoviště Schránky – 5. běh: výkon mikrokroků (2026-10-15)

Zadání člověka: „schránka výzkum pískoviště, dotáhni to do konce a implementuj to.“ Po 4. běhu
(`docs/navrhy/2026-10-15-nocni-smena.md`) mělo 16 disciplín „plán schválen ≥ 8/10, testy neběžely“; spustitelná buňka
K15 (`docs/schranka-bunka.md`) existovala jen v e2e testu. 5. běh ji pouští naostro: schválený mikrokrok každé disciplíny
se skutečně vykoná v klonu Tajemství opory a kontroly spustí nezávislý ověřovatel.

## Prostředí (mimo repa, nic se nepřenáší bez člověka)

| Co | Kde |
|---|---|
| základ | `P:\opora-piskoviste\base` = `git clone` Tajemství opory @ `b81b336` + kopie `node_modules` (445 vitest testů zelených) |
| složka vykonavatele | `P:\opora-piskoviste\<d>` (klon base; frontend disciplíny junction na `node_modules`) |
| zdroje kontrol | `P:\opora-piskoviste\tests\<d>\` – relativní cesty repa, položí se přes kopii vykonavatele (`run-checks --tests`); u pytestu i původní `backend/conftest.py` (pojistka proti živému LLM, protože ověřovatel `conftest.py` z kopie maže) |
| Python | `uv run --no-project --python 3.13 --directory backend --with-requirements requirements.lock …` (prostředí v uv cache, ne ve složce vykonavatele) |
| DB | kontejner `tajemstvi-postgres` (127.0.0.1:5433), `DATABASE_URL` nastaví ověřovatel i vykonavatel |
| stav a logy | `P:\opora-piskoviste\state\` |

Nástroje (trvalá kopie): `~/.claude/projects/<projekt>/loop-tools/run5/` – `sandbox5.py`, `seed_run5.py`,
`vault_propose5.py`, `prompts.md`.

## Role jednoho kola (aktéři jsou různí, server to hlídá)

1. **Autor kontrol** (Claude Sonnet, `Agent`): z schváleného mikrokroku napíše testy do `tests/<d>` a `checks.json`
   (1–4 příkazy ve tvaru §3 bod 1), ověří, že v klonu před výkonem **selžou**, a `seed_run5.py --apply` založí kořen
   „5. běh: …“ se sekcemi Zadání · Schválený mikrokrok · Kontroly · Prostředí výkonu.
2. **Navrhovatel** (Hermes přes `vault_propose5.py`): `weighed`, `synthesized` (mikrokrok beze změny; `checks` doplní
   nástroj přesně ze sekce Kontroly), `decided`, `learned`.
3. **Potvrzovatel** (Claude Sonnet, `Agent`, aktér `potvrz-<d>`): `yes`/`reject` podle `cycle.md`; u `synthesized` navíc
   porovná `checks` se sekcí Kontroly; `planned` + `placed` → karta s `checks` a `goal_mode: until_checks_pass`.
4. **Kritik** (ChatGPT přes `codex exec`): skóre plánu kola → `planScore`/`planApproved`, celá kritika jako research dítě.
5. **Vykonavatel** (`claude -p --model sonnet`, aktér `vykon-<d>`, odpojený proces v `P:\opora-piskoviste\<d>`,
   nástroje jen Read/Edit/Write + `uv`/`npm`/`python`/`git diff`): provede kroky karty, spouští stejné kontroly.
6. **Ověřovatel** (`opora_cycle.py run-checks`, aktér `over-<d>`): kopie složky bez conftest/pytest.ini, překryv
   `tests/<d>`, skutečný běh bez shellu, `propose verified` s `actual.run` (+ `planScore` kritika); výstup kontrol
   jako research dítě „Běh kontrol kola N“.
7. `verified` potvrdí potvrzovatel; neúspěch kola = `tests: fail` NEBO `planApproved: false` (§13); neúspěch a kolo < 3 →
   `no synthesized` → nové kolo (vykonavatel vidí výstup kontrol i kritiku); úspěch → `learned` (`pattern`), neúspěch v kole 3 →
   `antipattern`, „čeká na člověka“.

## Průběh

| Čas | Krok | Stav |
|---|---|---|
| 12:10 | prostředí: base klon, uv z lock souboru (31 health testů), vitest 445/445, Postgres | hotovo |
| 12:25 | nástroje run5 + šablony rolí | hotovo |
| 12:30 | pilot disciplína `test` (kontraktní test /api/v1/health): výkon i `run-checks` naostro | hotovo |
| 12:30–12:55 | autoři kontrol pro zbylých 15 disciplín (každý: testy, `checks.json`, zkušební běh v klonu = očekávané selhání, kořen „5. běh“) | hotovo |
| 12:35–13:25 | potvrzovatelé 16 disciplín paralelně (Hermes navrhuje, ChatGPT hodnotí, `claude -p` vykonává, `run-checks` ověřuje) | hotovo |
| průběžně | opravy nástroje za běhu: pravidlo `learned.kind` a nového kola podle §13 (`planApproved: false` = neúspěch), limity délek pro Hermese, kritik dostává zdroje pevných testů, vykonavatel bez prefixů proměnných a `cd`, oprava zaokrouhlení v testu `cloud` | hotovo |

## Výsledek

| Disciplína | Kola | Kritik | Testy | Kontroly (id→exit) | Poučení | Stav | Fragment | predErr |
|---|---|---|---|---|---|---|---|---|
| ai | 3 | 8 | pass | gateway→0 | pattern | kvalitní | 779b59fe | 0.33 |
| api | 1 | 8 | pass | api-handlery-chyb→0 | pattern | kvalitní | 1a89f06d | 0.0 |
| be | 1 | 8 | pass | credits-public→0 | pattern | kvalitní | e3f0ac26 | 0.0 |
| cache | 2 | 8 | pass | cache-test-api→0 | pattern | kvalitní | c041e953 | 0.17 |
| cloud | 3 | 7 | pass | doc-database-provider-decision→0 | antipattern | čeká na člověka | 0a43ad8e | 0.33 |
| content | 1 | 8 | pass | doc-style-guide→0 | pattern | kvalitní | 607b4037 | 0.33 |
| cx | 1 | 8 | pass | welcome-grant-db→0 | pattern | kvalitní | 29e989eb | 0.0 |
| data | 1 | 9 | pass | analytics-event-contract→0 | pattern | kvalitní | ed9154f1 | 0.0 |
| db | 1 | 8 | pass | idempotence-odpisu→0 | pattern | kvalitní | 0f820513 | 0.0 |
| devops | 3 | 8 | pass | heads→0, parity→0 | pattern | kvalitní | 505c573f | 0.33 |
| fe | 1 | 8 | pass | fe-opory-api→0 | pattern | kvalitní | aa68c779 | 0.0 |
| observability | 1 | 9 | pass | health-live→0 | pattern | kvalitní | 33d80bb2 | 0.0 |
| security | 1 | 9 | pass | cors-validator→0, cors-health→0 | pattern | kvalitní | b5180d32 | 0.0 |
| test | 2 | 8 | pass | openapi-contract→0 | pattern | kvalitní | 0091a0fd | 0.17 |
| ui | 2 | 9 | pass | sidenav-a11y→0, layout-nav→0 | pattern | kvalitní | cb2f9a77 | 0.17 |
| ux | 3 | 7 | pass | page-state-vitest→0 | antipattern | čeká na člověka | 13ab4d22 | 0.33 |

**14 z 16 disciplín má kvalitní výstup** (`verified` s `tests: pass` z doloženého běhu `run` ověřovatelem, plán ≥ 8/10, potvrzené
poučení `pattern`). `ux` a `cloud` skončily po 3 kolech „čeká na člověka“: kontroly prošly, ale kritik plán neschválil (ux: kritik
dostával oříznutý zdroj testu – limit v nástroji od té doby zvýšen; cloud: podklady D1–D9 nikdo nedodal, mikrokrok se o ně opírá).
`infra` zůstává z předchozích běhů „čeká na člověka“ (chybí ID služeb a URL). Všech 16 karet na plátně nese `checks` a
`goal_mode: until_checks_pass`; každý fragment má research děti „Kritika kola“ a „Běh kontrol kola N“ s výstupem kontrol.

Artefakty leží v klonech `P:\opora-piskoviste\<d>` (změněné soubory: cx 7, db 7, devops 10, ui 8, security 4, test 4, cache 3,
observability 3, ostatní 1–2). Do repa Tajemství opory je přenáší jen člověk (`git diff` v klonu).

Běh je **nahlášený, ne atestovaný** (`runTrust: reported`, `docs/schranka-bunka.md` §5): server příkazy nespouští a identita
aktérů je deklarovaná. Vykonavatel (`claude -p`) a ověřovatel (`run-checks`) jsou oddělené procesy s různými aktéry a testy ležely
mimo složku vykonavatele; to je vše, co řez zaručuje.

## Co pevné kontroly NEdokládají (nepokrytá akceptace, podle hlášení potvrzovatelů a kritika)

„Kvalitní“ = kontroly prošly a kritik schválil plán. Části `done`, které žádná kontrola neměří, zůstávají neověřené:

| Disciplína | Nepokryto |
|---|---|
| test | sběr nového testu skriptem `be2:test`, izolace a úklid paměti health, zápis `jsonschema` v `pyproject.toml` (kontrola čte jen lock) |
| observability | tělo odpovědi `/live`, zapojení pod oba prefixy `/api/v1` i `/api` v `create_app()`, Dockerfile jen textově |
| ai | pořadí redakce vs. escapování, přesný tvar mezer, chování pro jiné pořadí rolí; výpis zdroje pro kritika byl zkrácený |
| api | větev HTTPException s neřetězcovým detailem (bez testu), vážené Accept, skutečné validační chyby z routerů |
| cache | mapa metoda+cesta zafixovaná testem, alias `/api/*`, kde přesně hlavičku nastaví middleware při 500 |
| security | CSRF, preflight OPTIONS, alias `/api/health`, `allow_credentials` jen přes projev v hlavičce |
| be, db, cx | DB scénáře doložené jen exit kódem; souběh ověřen výsledkem, ne mutací (lock vs. ON CONFLICT); cx migrace 0028 aplikovaná na sdílené DB |
| data | anonymita a právní tvrzení jen jako slova v docstringu; architektonické hlídače (import-linter) neběžely |
| devops | skutečné propadnutí kódu přes npm a mise (parita jen textově), pomocné testy navrhovatele se nikdy nespustily |
| fe | proxy, prohlížečová relace 201/200, 404 aliasu, health – jen jednotkový test klienta |
| ui | vzhled značky a fokus, výchozí `/settings` bez vynuceného active, aktivace z `/chat` s otevřeným modalem |
| content | pravost citací GDPR/EDPB/ÚOOÚ a porovnání s EUR-Lex, uživatelský test (neprovedeno), právní schválení (neschváleno) |
| ux (čeká) | ruční ověření NVDA + Firefox, texty empty/blocked; kritik posuzoval zkrácený zdroj testu – plán znovu posoudit s úplným zdrojem (limit zvýšen) |
| cloud (čeká) | podklady D1–D9 nedodané; dokument stojí jen na kódu repa a testech, pravdivost tvrzení neověřena |

Dostupné cesty: nepokryté body zúžit do `nonGoals`, nebo k nim dodat další pevnou kontrolu (změna kontrol = člověk, nový běh,
hotové běhy se zpětně nemění); ux znovu posoudit plán s úplným zdrojem; cloud dohledat D1–D9 v existujících zdrojích.

## Poznatky pro Schránku

- **Plán schválen ≠ testy prošly platí i obráceně:** 6 disciplín mělo v kole 1 prošlé kontroly a plán 7/10. Server to správně
  bere jako neúspěch (`verified_outcome`), ale zadání rolí to zprvu neřešilo; sjednoceno (nové kolo při `planApproved: false`,
  poučení `antipattern`).
- **Kritik potřebuje zdroje pevných testů a diff,** jinak opakuje „pokrytí done nelze potvrdit“ a kolo je ztracené (ux). Doplněno
  do podkladu kritika; chybí ještě diff klonu a souhrn pytestu (passed/skipped) v `run` – potvrzovatelé u DB testů kontrolu
  spouštěli znovu ručně, aby vyloučili tichý skip.
- **Překryv testů ověřovatelem je kontrakt, ne vada:** bez výslovné věty v promptu kritik i navrhovatel vymýšleli kroky „doložit
  originál testu před překrytím“ a `decided: other`.
- **Kontroly jsou měřítko napříč koly, proto musí být správné před výkonem:** chyba zaokrouhlení v testu `cloud` prohrála kolo 1
  předem. Autor kontrol má test ověřit na referenčním řešení (udělal to jen `be`).
- **Mikrokrok s nedostupnými vstupy (cloud D1–D9) nebo s ručními kroky (ux NVDA) nemůže dosáhnout 8/10;** takové kroky patří do
  `nonGoals` nebo k člověku, ne do `done`.
- **Hermes překračuje limity** (`done` > 500) a nerespektuje pravidlo `kind`; nástroj teď texty zkracuje a pravidlo opakuje.
- **Vykonavatel pod allowlistem** nesmí psát `VAR=… příkaz` ani `cd … &&`; dvě disciplíny proto testy lokálně nespustily (kontroly
  přesto u ověřovatele prošly).

## Co zůstává na člověku

1. Přenos artefaktů z klonů do Tajemství opory (po přečtení `git diff`), nebo jejich zahození.
2. `ux`, `cloud`, `infra`: rozhodnout, zda mikrokrok zúžit (bez ručních kroků a nedostupných vstupů), nebo dodat vstupy.
3. Atestace běhu (`docs/schranka-overovatel-navrh.md`) zůstává BLOCKED – architektonické rozhodnutí.
4. Úklid pískoviště na disku (`P:\opora-piskoviste`, ~1 GB s node_modules) a kontejneru `tajemstvi-postgres`, až nebude třeba.

