# Struktura Tajemství opory: architektura, nastavení, složky, dokumentace

Stav k 2026-10-14. Jde o rozbor, nic se neměnilo. Zkratky: **TO** = Tajemství opory, spravovaný klon `P:\opora-data\projects\41a6776519694319a3aaf7ff453c3dfc\main` (1203 souborů v gitu). **AM** = Ample (`I:\1. Projekty\01_ITNeskola\06_AmpleLab\ample`). **PL** = toto repo (OPORA canvas).
Značky: **[F]** = fakt ověřený čtením souboru, příkazem nebo citovaným zdrojem. **[D]** = doporučení. **[?]** = neověřeno.

---

## 1. Shrnutí (doporučení)

1. **[D] Strom neodráží strom komponent.** Rodič skládá dílky importem, ne vnořenou složkou. Zakázat `components/…/components/`. Feature v TO = plochá složka `features/<doména>/<dílek>/` a v ní `.tsx` + `.css` + `.test.tsx` vedle sebe. Šuplíky (`api/`, `model/`, `hooks/`) patří jen na úroveň domény, ne ke každému dílku. Nejhorší cesta se tím zkrátí ze 109 na 83 znaků.
2. **[D] Rozpočet cesty jako brána v CI:** relativní cesta v gitu nejvýš **100 znaků** (varování od 90), nejvýš **8 segmentů**, zakázané vzory `components/*/components/` a `domain/*/*/*/`. Kontrolu dělá skript v `scripts/ci/` v režimu ratchet: seznam výjimek se smí jen zmenšovat. Dnes má 10 souborů víc než 100 znaků a 45 víc než 90.
3. **[D] `.claude/` je jen pro nástroje agentů** (settings, skills, commands, hooks, rules). `.claude/workbench/axis-x` (194 souborů) smazat. 11 jeho `.py` je bajtově shodných s `backend/…/dualita/jadro/` [F]. Katalog funkcí (`funkce/osa-x/**`) převést do `docs/reference/dualita/` (jeden soubor na funkci místo pěti), nebo do karet plátna.
4. **[D] Backend: zachovat anatomii modulu** (`public.py`, `api/`, `domain/`, `adapters/`, testy vedle), ale pod `domain/` povolit nejvýš jednotku a jednu podúroveň. Kernel OporaBrain vyčlenit jako samostatný modul `modules/kernel/` se strážcem importů. Jména složek jen anglicky (`jadro` → `core`, `scenare` → `sims`).
5. **[D] Jedna konfigurace na vlastníka a jeden soupis.** Backend: `pydantic-settings` (už se používá), vrstvy *výchozí v kódu → kořenový `.env` (jen lokálně) → proměnné prostředí*. Cesta k `.env` se počítá absolutně od kořene repa, ne od CWD. Kořenový `.env.example` je jediný soupis všech proměnných a test hlídá, že sedí se třídami `Settings`. Ve frontendu jen veřejné `VITE_*`, typované v jednom `shared/config/env.ts`. Lepší je vůbec žádná URL backendu: proxy `/api` stejně jako v AM.
6. **[D] Jedna brána a jeden spouštěč příkazů:** `mise run check` / `check-full`. Přejmenovat `be2:*` na `be:*` a v dokumentech nikde nezmiňovat přímé `npm run be2:check`. Rozpor zaznamenal už `docs/navrhy/2026-10-14-vyvoj-tajemstvi-opory-v-platne.md` §1.
7. **[D] Dokumentace podle Diátaxis plus ADR:** `docs/{tutorials,how-to,reference,explanation,adr}`. Zdroje pravdy musí být v gitu: `AGENTS.md` dnes odkazuje na `pipeline/kontext/produkt.md`, ale `pipeline/` je v `.gitignore` [F]. Historii nese git a ADR, ne komentáře v kódu (vzor „dokument smazán v 351d8f7“ je v `config.py`, `.env.example` i `pyproject.toml`).
8. **[D] Instrukce pro agenty:** `AGENTS.md` = kanonický rámec, kořenový `CLAUDE.md` = `@AGENTS.md` + jen specifika Claude Code. Vnořené `CLAUDE.md` jen ve `frontend/`, `backend/`, `database/`, každé pod 200 řádků. Pravidla vázaná na cesty patří do `.claude/rules/` s `paths:`. CI kontroluje mrtvé odkazy.
9. **[D] Škálování znamená hranice, ne mikroslužby.** Bezstavové procesy `api` a `worker` (už existují), session a rate limit v Redis/DB, logy na stdout, migrace jako samostatný krok vydání. Moduly s vlastními tabulkami a přístupem jen přes `public.py`, takže je jde později vyjmout. Hranice hlídá stroj: import-linter a dependency-cruiser.
10. **[D] Migrace po malých krocích s `git mv`.** Pořadí: brána délky (ratchet) → smazání workbench → aliasy `@/` → přesun `prophet-two` → backend kernel/dualita → konfigurace → dokumentace. Po každém kroku musí projít `mise run check-full` a počet testů se nesmí změnit.

---

## 2. Současný stav TO (fakta)

### 2.1 Čísla

| Míra | Hodnota [F] (`git ls-files`) |
|---|---|
| souborů v gitu | 1203 (backend 530, frontend 331, `.claude` 202, docs 45, database 42, tools 18) |
| délka relativní cesty | medián 56, p90 76, **max 109** |
| cest > 80 / > 90 / > 100 znaků | 71 / 45 / **10** (všech 10 je v `pages/oracle/components/prophet-two/components/`) |
| hloubka (segmenty) | 9 segmentů: 57 souborů, 10 segmentů: 50 souborů. Hloubka > 8: 107 souborů (76 `frontend/app/src/pages/oracle/components`, 31 `backend/app/modules/engine/domain/axes`) |
| soubory s `components/…/components/` | **46** |
| nejčastější segmenty | `app` 848×, `modules` 433×, `components` 267×, `domain` 234×, `pages` 221×, `oracle` 188× |
| relativní importy `../../../` a hlubší | 51 (41× čtyři úrovně, 1× pět: `prophet-two/api/prophet-two-api.ts:1` → `'../../../../../lib/opory-api'`) |
| aliasy cest | žádné (`frontend/app/tsconfig.json` nemá `paths`, `vite.config.js` nemá `resolve.alias`) |
| soubory .py/.ts/.tsx nad 300 řádků | 87. Největší: `backend/app/test_opora_brain_purity.py` 1419, `backend/app/modules/engine/public.py` **1215** (fasáda modulu) |

### 2.2 Nejdelší cesty

```
109 frontend/app/src/pages/oracle/components/prophet-two/components/attribution-choice/AttributionChoice.test.tsx
107 …/prophet-two/components/branch-crossroads/BranchCrossroads.test.tsx
106 …/prophet-two/components/risk-profile-quiz/RiskProfileQuiz.test.tsx
 91 backend/app/modules/opora_brain/domain/kernel/deterministic_hash/test_hashing_properties.py
 90 backend/app/modules/opora_brain/domain/kernel/canonical_bytes/test_canonical_properties.py
 83 backend/app/modules/engine/domain/axes/dualita/jadro/scenare/long_run_simulation.py
```

### 2.3 Proč to padalo ve worktree [F]

Delší ze dvou rozpočtů je absolutní cesta. Pro git platí `MAX_PATH` = 260 znaků včetně koncové NUL (Microsoft). Prefix worktree býval `…\Opora-control-center-canvas\.data\production\projects\<32>\worktrees\<uuid36>\`, což je 190 znaků. S cestou 109 znaků to dělá **299**. Commit `71d4c2c` v PL zapnul `core.longpaths`, zkrátil složku worktree na 8 znaků a přesunul data na `P:\opora-data`. Prefix má teď 75 znaků a nejhorší soubor 184. **Ale** generované soubory jsou delší než zdroj. Například `…/canonical_bytes/__pycache__/test_canonical_properties.cpython-313-pytest-8.4.2.pyc` má relativně 128 znaků. Na `MAX_PATH` navíc dál narážejí Explorer, `cmd.exe` a nástroje, které nejsou long-path-aware (Git for Windows FAQ). `core.longpaths` je proto záplata, ne řešení.

### 2.4 Struktura a bolesti (s doklady)

| Oblast | Co je [F] | Bolest |
|---|---|---|
| Kořen | `backend/ frontend/ database/ docs/ tools/ scripts/ infrastructure/ .claude/` + 20 konfiguračních souborů | `tools/` i `scripts/` znamenají totéž. `infrastructure/` obsahuje jen 2 `CLAUDE.md` bez kódu |
| Frontend | yarn workspaces `frontend/{app,web,shared}`. `app/src/{app,pages,components,hooks,lib}`. **`features/` neexistuje**, přestože ji popisuje `frontend/CLAUDE.md` | 221 z 294 souborů `src/` je v `pages/`, z toho 135 v `pages/oracle`. Doména `prophet-two` (79 souborů) je schovaná jako „komponenta stránky“ |
| Oracle | `pages/oracle/components/` má 20 složek, mimo jiné `prophet/`, `prophet-two/`, `prophet-secondary/`, `prophet-window/`, `prophet-window-controlled/` | Číslované a variantní názvy porušují vlastní zákaz číslování (`backend/CLAUDE.md` „zakázaná slova a číslování stejné jako FE“) |
| Backend | `backend/app/{entrypoints,lib,modules}`, 11 modulů. Anatomie `public.py/api/domain/adapters` popsaná v `backend/CLAUDE.md` | Dobrý vzor. Hloubka roste v `opora_brain/domain/kernel/<unit>/` (9 jednotek) a `engine/domain/axes/dualita/jadro/scenare/` |
| Jména | `backend/CLAUDE.md`: „názvy vždy anglicky“ | 37 souborů pod českými složkami (`jadro`, `scenare`, `grid_projekce`) nebo s českými názvy (`banka.py`, `derivace.py`, `uzel.py`). V `config.py` pole `session_ttl_hodin`, `smtp_heslo`, `max_delka_tela_bajtu` |
| `.claude/` | `workbench/axis-x` má 194 souborů: duplikát jádra dualita (11 `.py` shodných, ověřeno `cmp`), 162 souborů katalogu funkcí (5 souborů na funkci) a vlastní `tests/` | Kód mimo aplikaci, duplicitní. README odkazuje na neexistující `dilna/osa-x` a staré české názvy modulů |
| Testy | vedle kódu (`test_*.py`, `*.test.tsx`), 268 souborů | Dobré. Výjimka `.claude/workbench/axis-x/tests/` |
| Migrace | `database/migrations/versions/0001…0027_*.py`, `database/alembic.ini`, guardy s testy | Dobré, jedno místo |
| Konfigurace | `backend/app/lib/config.py` (312 ř., pydantic-settings, `env_file=".env"` relativně k CWD). `.env.example` ×4 (kořen pro compose, `backend/`, `frontend/app/`, `frontend/web/`). `mise.toml [env] DATABASE_URL`. Porty jsou natvrdo ve `vite.config.js` (3002), v `package.json` (8010) a v defaultech `config.py` (CORS 3002) | Čtyři `.env` a tři místa s porty. `frontend/app/.env.example` má `VITE_BACKEND_URL` :8000 (starý backend) i `VITE_BACKEND2_URL` :8010 |
| Příkazy | `package.json` scripts (`be2:*`, `fe:*`), `mise.toml` tasks, `yarn --cwd`. `dev:be2` s windowsovou cestou `.venv-app\Scripts\python` | Tři spouštěče. Legacy „be2“ přežívá v SPEC uzlů |
| Hranice | import-linter v `backend/pyproject.toml` (706 ř.): 11 kontraktů „X: vnitřek privátní“ a v každém ručně vyjmenovaných všech 10 ostatních modulů. dependency-cruiser `frontend/.dependency-cruiser.cjs` | Nový modul znamená upravit 11 míst (návod v `backend/CLAUDE.md`). Komentáře v kontraktech nesou historii |
| Dokumentace | 219 `.md`. 7× `CLAUDE.md` + `AGENTS.md` + `.github/copilot-instructions.md`. `docs/agent-system/` (6), `docs/opora-workflow/` (plány, TODO), `docs/opora/` (produkt), 27× `PRD.md`/`SPEC.md` v kódu | Zdroje pravdy v `pipeline/` mimo git. Mrtvé odkazy: `frontend/CLAUDE.md` → `docs/architecture/` (neexistuje), `backend/CLAUDE.md` a `frontend/CLAUDE.md` → sekce `<lsp-vyhledavani>` v kořenovém `CLAUDE.md` (neexistuje), `backend/.env.example` → `docs/runbooks/db-provoz.md` (neexistuje), `backend/CLAUDE.md` „router v `app/main.py`“ (to je jen alias na `entrypoints/api.py`) |

---

## 3. Co se osvědčilo a co bolí v AM a PL

### 3.1 Ample

| Osvědčilo se [F] | Doklad |
|---|---|
| Jeden `package.json`, `vite.config.ts`, `tsconfig.json`, `pyproject.toml` v kořeni. Jeden `node_modules` a jeden `.venv` | `CLAUDE.md` „Commands“. Kořen AM |
| Alias `@/` = `frontend/` | `frontend/CLAUDE.md` ř. 4 |
| Jeden `.env` v kořeni → `backend/app/settings.py` (67 řádků). Názvy polí = názvy proměnných (`API_PORT`, `CACHE`). Výběr adaptéru přes `Literal["memory","redis"]` | `backend/app/settings.py`, `.env.example` |
| Proxy `/api` (Vite v dev, nginx v produkci), takže žádný CORS a žádná URL backendu ve FE | `frontend/CLAUDE.md` ř. 2–3 |
| Plochý backend podle vrstev `core/` (čistá doména) ← `rag/` ← `api/`, `cache/`, `app/` (skládání). Tři kontrakty import-linter včetně zákazu frameworků v `core` | `pyproject.toml` `[tool.importlinter]` |
| `GLOSSARY.md` (pojem + *Avoid*), `docs/adr/0001-*.md` | kořen, `docs/adr/` |
| One-Pattern Rule, „gold standard“ vzory | `CLAUDE.md`, `frontend/CLAUDE.md` „Vzory“ |
| Hloubka max 7 segmentů, max 102 znaků | `git ls-files` |

| Bolí [F] | Doklad |
|---|---|
| Šuplík `components/` přidává segment ke každému dílku a opakují se jména: `frontend/settings/organization/organization-settings-page/components/OrganizationSettingsPage.test.tsx` (102 znaků) | `git ls-files` |
| `project/widget-lab` má 154 souborů v jedné feature. Míchá češtinu a angličtinu (`widget-mock/mock-prvky`, `technika-panel`) | `git ls-files frontend/project/widget-lab` |
| Pracovní poznámky v kořeni (`upgrade-opora.md`, `plan-dalsich-vrstev.md`, `image*.png` na disku) | kořen AM |
| ADR 0001 nese dodatky „Aktualizace 2026-10-05“ místo nového ADR, který by ho nahradil | `docs/adr/0001-backend-v2-python.md` |

### 3.2 OPORA canvas (PL)

| Osvědčilo se [F] | Doklad |
|---|---|
| Otázkový strom „kam soubor patří“ (vidí to uživatel → frontend…) | `docs/pravidla-struktury.md` §pravidla 1–5 |
| Rodič skládá, data dolů, události nahoru. Logika bez Reactu v `logic/` s testem vedle | `docs/pravidla-struktury.md` „Skládání frontendu“ |
| BEM s příběhovým komentářem, jeden CSS na feature | tamtéž, bod 4 |
| Jediné místo pro rozdíly mezi druhy projektu | `frontend/shared/project-capabilities/logic/project-capabilities.ts` |
| `opora.toml` (verzovaný) + `opora.local.toml` (mimo git) + profily (`preview`, `dev`). Tajemství výslovně jen v env | `opora.toml` ř. 1–3, 27 |
| Router jen v `backend/api/<prostředí>/`, logika v modulu | `CLAUDE.md`, `backend/STRUCTURE-PLAN.md` |

| Bolí [F] | Doklad |
|---|---|
| Šuplíky `components/ logic/ styles/` u **každého** dílku: 663 souborů frontendu leží v šuplíku a hloubka 6–7 segmentů je běžná | `git ls-files frontend` |
| Pravidlo „~200 řádků“ se nedodržuje: `frontend/app/components/App.tsx` má 1797 řádků. Pravidlo bez strojové kontroly nefunguje | `wc -l` |
| `opora.toml` sice prohlašuje, že je jediný zdroj, ale `backend/app/factory.py:70,88` čte i `OPORA_CANVAS_DATA` a `OPORA_CANVAS_PORT` s vlastními defaulty. Dva zdroje stejné hodnoty | `factory.py` |
| `docs/pravidla-struktury.md` obsahuje ručně psaný „Skutečný stav“ (výpis složek), který zastarává. `docs/` je ploché (30 souborů v kořeni) a `docs/README.md` má jeden řádek | soubory |
| Konfigurace TOML je vhodná pro **lokální desktopovou aplikaci**. Pro webovou službu se statisíci uživatelů je správná vrstva proměnná prostředí (12-factor), viz §5 | `opora.toml` |

**[D] Co z toho převzít do TO:** otázkový strom umístění, skládání rodič → dílek, testy vedle, BEM s příběhem, jedno místo pro variantní chování, profilovou konfiguraci jen pro lokální vývoj. **Nepřebírat:** šuplíky u každého dílku a ruční výpisy stavu v dokumentech.

---

## 4. Doporučená struktura [D]

### 4.1 Strom

```
tajemstvi-opory/
├── AGENTS.md                 # kanonický rámec pro agenty (≤ 200 ř.)
├── CLAUDE.md                 # @AGENTS.md + specifika Claude Code
├── README.md                 # co to je, 10min start → docs/tutorials/
├── .env.example              # JEDINÝ soupis proměnných (BE, FE VITE_*, compose)
├── mise.toml                 # nástroje + JEDINÝ vstup příkazů (check, check-full, dev)
├── package.json              # workspaces + atomické skripty (volá mise i CI)
├── docker-compose.yml        # lokální backing services (PG, Redis)
├── .claude/                  # jen settings.json, skills/, commands/, hooks/, rules/
├── .github/                  # workflows/, PULL_REQUEST_TEMPLATE.md, copilot-instructions.md
├── backend/
│   ├── pyproject.toml        # závislosti, ruff, mypy, import-linter (generovaný blok)
│   ├── Dockerfile
│   └── app/
│       ├── entrypoints/      # api.py, worker.py (kompoziční kořeny, čtou Settings)
│       ├── lib/              # product-blind: config, db, redis, events, observability, llm…
│       └── modules/
│           └── <module>/     # users, credits, oracle, dna, chat, engine, privacy, audit,
│               ├── README.md #   monitoring, news, brain, kernel
│               ├── public.py
│               ├── <module>_settings.py   # volitelné, env_prefix "<MODULE>_"
│               ├── api/      # <module>_router.py, <module>_schemas.py
│               ├── domain/
│               │   └── <unit>/[<sub>/]    # MAX dvě úrovně
│               └── adapters/ # <module>_models.py, <module>_repo_sql.py
├── database/
│   ├── alembic.ini
│   ├── migrations/versions/NNNN_<module>_<popis>.py
│   └── seed/
├── frontend/
│   ├── app/                  # @tajemstvi/app
│   │   ├── vite.config.ts    # alias @ → src, proxy /api
│   │   └── src/
│   │       ├── app/          # routes.ts, providers/, layout/
│   │       ├── pages/<name>/ # TENKÉ: <Name>Page.tsx skládá features
│   │       ├── features/<domain>/
│   │       │   ├── <slice>/  # Slice.tsx, slice.css, Slice.test.tsx (PLOCHÉ)
│   │       │   ├── api/  model/  hooks/       # šuplíky jen na úrovni domény
│   │       │   └── README.md
│   │       └── shared/       # ui/, api/, lib/, config/env.ts
│   ├── web/                  # @tajemstvi/web (stejná pravidla)
│   └── shared/               # @tajemstvi/shared (theme.css, sdílené UI)
├── docs/                     # viz §6
└── scripts/                  # ci/, db/, security/, dev/  (sloučit tools/ sem)
```

### 4.2 Pravidla

| Pravidlo | Znění | Proč |
|---|---|---|
| **R1 plochý dílek** | Složka komponenty obsahuje soubory, ne podsložky `components/`. Pod-dílek je sourozenec ve stejné doméně, vztah rodič → dítě vyjadřuje import. | React doporučuje nejvýš 3–4 úrovně vnoření, protože hluboké relativní importy se těžko udržují (React FAQ). FSD dělí kód na *slices* (doména) a *segments* (`ui`, `api`, `model`) jen o jednu úroveň |
| **R2 šuplíky na doméně** | `api/`, `model/` (čistý TS + testy), `hooks/` jen přímo pod `features/<domain>/` | Zachová oddělení „logika bez Reactu“ z PL bez segmentu navíc u každého dílku |
| **R3 povýšení** | Kód jedné stránky může žít v `pages/<name>/` (plochý). Jakmile má vlastní model nebo víc než ~10 souborů, je to `features/<domain>/`. Sdílené ve dvou doménách → `shared/` | Pravidlo z `frontend/CLAUDE.md` už existuje, jen se neprovádí (`features/` chybí) |
| **R4 importy** | Vše přes `@/…` (tsconfig `paths` + Vite `resolve.alias` nebo `resolve.tsconfigPaths`). Relativně jen v rámci slice (`./`) | TS `paths` nemění emitované importy, bundler musí mapovat také (TS docs). Vite vyžaduje absolutní cílové cesty aliasu |
| **R5 backend hloubka** | `modules/<m>/domain/<unit>/[<sub>/]soubor`, nic hlubšího | Totéž pravidlo „potomek = podsložka jednotky“ z `backend/CLAUDE.md`, ale s mezí |
| **R6 jména** | Složky a soubory anglicky. Bez čísel a variant (`-two`, `-secondary`, `v2`), místo nich význam. Segment neopakuje rodiče (`settings/organization/organization-settings-page` → `settings/organization/page`) | Opakování stojí znaky a nic neříká |
| **R7 rozpočet** | Relativní cesta ≤ 100 znaků (varování 90), ≤ 8 segmentů. Délka slice ≤ 24 znaků | 260 − 1 (NUL) − prefix worktree ~80 − rezerva na generované soubory ~40 (`__pycache__`, `.pytest_cache`, coverage) ≈ 140. Rozpočet 100 dává rezervu i pro klon v hluboké uživatelské složce |
| **R8 testy** | Vždy vedle souboru (`test_<x>.py`, `<X>.test.tsx`). E2E jediná výjimka: `frontend/app/e2e/` | Platí už dnes v TO, AM i PL |
| **R9 styly** | `slice.css` vedle `Slice.tsx`. BEM blok = jméno slice. Tokeny jen z `@tajemstvi/shared/theme.css` | PL pravidlo bez složky `styles/` |
| **R10 migrace** | Jen `database/migrations/versions/`. Název `NNNN_<module>_<popis>.py`. Tabulky s prefixem modulu (už platí) | Jedno místo. Prefix modulu v názvu migrace usnadní pozdější vyjmutí modulu |
| **R11 sdílený kód** | BE: technické → `app/lib/` (product-blind, test `test_lib_is_product_blind.py` existuje), doménové → `public.py` vlastníka. FE: `shared/` nebo `@tajemstvi/shared` | Už zavedeno v TO, jen to dodržet |
| **R12 velikost** | Soubor ≤ ~300 řádků (testy ≤ ~600), hlídá skript (ratchet). `engine/public.py` (1215) rozdělit na `public.py` (re-exporty) + `public_<oblast>.py` | Pravidlo bez kontroly nefunguje (příklad PL `App.tsx`) |

### 4.3 Proč ne src layout v Pythonu (teď)

`src/` layout chrání před importem nenainstalované kopie a hodí se pro **distribuované balíčky** (packaging.python.org). TO je aplikace nasazovaná v Dockeru. Testy běží nad stromem a `backend/app` už je jediný kořen balíčku. Přechod by přidal segment a přejmenoval každý import. **[D]** neprovádět. Vrátit se k tomu, až by se nějaký modul stal samostatně publikovaným balíčkem.

### 4.4 FastAPI

TO je FastAPI [F] (`backend/pyproject.toml` ř. 7 `fastapi>=0.115`, `AGENTS.md` „FastAPI modulární monolit“). Oficiální vzor „Bigger Applications“ je `APIRouter` na modul a `app.include_router(...)` v jednom kořeni. TO to plní: `modules/<m>/api/<m>_router.py` a kořen `entrypoints/api.py`. **[D]** Smazat alias `backend/app/main.py` a opravit `backend/CLAUDE.md`, který ještě odkazuje na `app/main.py`.

---

## 5. Globální nastavení [D]

### 5.1 Princip

- **Konfigurace = to, co se liší mezi nasazeními**, a patří do proměnných prostředí. Nastavují se jednotlivě, nikdy jako balík pojmenovaných „prostředí“ (12-factor, Config). Backing services (PG, Redis, SMTP, LLM) jsou připojené zdroje vyměnitelné změnou URL bez zásahu do kódu (12-factor, Backing services).
- **Jedno místo na vlastníka, jeden soupis pro člověka.** Infrastruktura (DB, Redis, CORS, cookie, pozorovatelnost, LLM brána) patří do `app/lib/config.py`. Nastavení modulu (rate limity privacy, sweep, brain) patří do `modules/<m>/<m>_settings.py` s `env_prefix="<M>_"`. Instance se tvoří jen v `entrypoints/` a do modulů jdou jako závislost. Modul tak jde vyjmout i se svou konfigurací.
- **Soupis:** kořenový `.env.example`, sekce `# backend`, `# frontend (VITE_, veřejné!)`, `# compose`. Test `scripts/ci/test_env_example_parity.py` projde všechny třídy `BaseSettings` a ověří, že každé pole má řádek v `.env.example` a naopak.

### 5.2 Vrstvy (od nejnižší priority)

| Vrstva | Backend | Frontend | Kde žije |
|---|---|---|---|
| 1. výchozí | default pole v `Settings`, bezpečný pro dev (fail-closed: žádné tajemství, SMTP vypnuté) | default v `env.ts` | kód |
| 2. lokální soubor | kořenový `.env` (gitignored). Cesta absolutně: `Path(__file__).parents[N] / ".env"`, protože pydantic-settings řeší relativní `env_file` vůči **CWD** [F, docs] | `.env.local` (Vite načítá `.env` → `.env.local` → `.env.[mode]` → `.env.[mode].local`) | disk vývojáře |
| 3. prostředí | proměnné procesu mají přednost před dotenv [F, docs] | proměnné shellu mají přednost před soubory [F, docs] | platforma nasazení / secret manager |
| (4.) test | `Settings(**kwargs)`: init kwargs mají nejvyšší prioritu [F, docs] | `vi.stubEnv` | testy |

Pořadí jde měnit přes `settings_customise_sources` (Pydantic). **Nepoužívat** verzované `config/prod.toml` s produkčními hodnotami: per-env soubory v repu jsou přesně to „seskupení do prostředí“, před kterým 12-factor varuje. Profilový TOML jako `opora.toml` v PL je v pořádku jen pro lokální nástroje.

### 5.3 Tajemství

- Typ `SecretStr` (TO už má u `smtp_heslo`; rozšířit na `anthropic_api_key`, `cron_token`, hesla v DSN). Nikdy v `VITE_*`: Vite takové proměnné vloží do klientského bundlu [F, Vite docs].
- Produkce: secret manager nebo proměnné platformy. Lokálně `.env`. V repu jen placeholder `zmen-me-…`, který už dnes hlídá validátor v `config.py`. Gitleaks v `mise run secrets` zůstává.
- `APP_ENV` jen jako přepínač bezpečnostních pojistek (SMTP jen v `prod` už funguje). Nikdy ne jako selektor sady hodnot.

### 5.4 Typovaný frontend

- `src/shared/config/env.ts`: jedno čtení `import.meta.env`, validace při startu a export zmrazeného objektu. `vite-env.d.ts` rozšíří `ImportMetaEnv` (Vite docs). Dílek nikdy nečte `import.meta.env` sám (lint pravidlo). Je to obdoba `project-capabilities.ts` v PL.
- **Žádná URL backendu ve FE:** dev proxy `server.proxy['/api']` ve `vite.config.ts`, v produkci reverse proxy na stejném originu (vzor AM). Zmizí `VITE_BACKEND_URL`, `VITE_BACKEND2_URL`, CORS seznam i port 3002 v `config.py`. Stejný build jde nasadit všude (build once, deploy many).
- Porty patří jen do `.env.example` → compose, `vite.config.ts` (čte `process.env`) a `mise.toml`. Nikde jinde natvrdo.

### 5.5 Pojmenování proměnných

Anglicky, `UPPER_SNAKE`, prefix vlastníka: `DB_POOL_SIZE`, `PRIVACY_DELETE_RATE_LIMIT`, `BRAIN_ENABLED`. Česká pole (`SESSION_TTL_HODIN`, `SMTP_HESLO`) přejmenovat s `validation_alias=AliasChoices(new, old)` na jedno vydání. Pak starý název odstranit.

---

## 6. Dokumentace [D]

### 6.1 Kam co patří

| Druh (Diátaxis) | Složka | Obsah v TO | Odkud se to přesune |
|---|---|---|---|
| Tutorial (učení) | `docs/tutorials/` | `start-here.md`: lokální běh za 10 minut | nové, z kousků `README` a `.env.example` |
| How-to (úkol) | `docs/how-to/` | přidat modul, přidat nastavení, udělat migraci, přidat stránku, runbooky provozu (`how-to/ops/`) | návody z `backend/CLAUDE.md` („nový modul = …“), `database/CLAUDE.md` |
| Reference (stroj) | `docs/reference/` | `config.md` (generovaný ze `Settings`), `modules.md` (generovaný z docstringů `public.py`), OpenAPI (generuje FastAPI), `glossary.md`, `dualita/<funkce>.md` | `.claude/workbench/axis-x/funkce/**` (5 souborů na funkci → 1) |
| Explanation (proč) | `docs/explanation/` | `architecture.md` (moduly, toky, hranice), `product.md`, `opora-mechanism.md`, `invariants.md`, `agent-system/` | `pipeline/kontext/produkt.md` (**do gitu**), `docs/opora/*`, `docs/agent-system/*` |
| Rozhodnutí | `docs/adr/NNNN-slug.md` | Nygard: Title, Status, Context, Decision, Consequences. Číslování monotónní, zrušené rozhodnutí se označí *superseded* a nemaže se | rozhodnutí roztroušená v komentářích (`config.py` „OPRAVA B1“, `ci.yml` „PRAVIDLO ETAPY D4“), `docs/opora-workflow/01-ROZHODNUTI.md` |
| Plán / úkoly | **plátno OPORA** (karty, sektory) | – | `docs/opora-workflow/00-PLAN.md`, `uzly/*/TODO.md` (podle `2026-10-14-vyvoj-tajemstvi-opory-v-platne.md` §4) |

Diátaxis rozlišuje čtyři potřeby a k nim čtyři formy dokumentace. Reference je „technický popis stroje a jak ho obsluhovat“ (diataxis.fr).

### 6.2 Dokument u kódu

- **README modulu** (`modules/<m>/README.md`, `features/<d>/README.md`) je jedno místo pro účel, veřejné API, eventy, tabulky a nastavení modulu. Nejvýš ~60 řádků. Docstring `public.py` jen odkazuje (dnes je hranice v docstringu: rozhodnout se pro jedno). Generátor `docs/reference/modules.md` čte README.
- `PRD.md` / `SPEC.md` u uzlů OporaBrain zůstávají (kód a testy je čtou).
- **Komentář v kódu říká proč teď, ne historii.** Odkazy „commit 748d917; dokument smazán v 351d8f7“ nahradit odkazem na ADR, nebo je smazat.

### 6.3 Agenti

- `AGENTS.md` (kanonický) a kořenový `CLAUDE.md` s prvním řádkem `@AGENTS.md`. Claude Code umí `@path` importy (relativně k souboru) i přímé čtení `AGENTS.md` (Claude Code docs, Memory).
- Vnořené `CLAUDE.md` se načítají až při práci v podsložce. Doporučená velikost je pod 200 řádků a pravidla platná jen pro část kódu patří do `.claude/rules/*.md` s `paths:` (tamtéž). **[D]** Ponechat `frontend/`, `backend/`, `database/CLAUDE.md`. `infrastructure/*/CLAUDE.md` a `frontend/app/assets/CLAUDE.md` převést na `.claude/rules/brand.md` (`paths: frontend/**/*.css`) a podobně.
- Odporující si instrukce rozhodne model náhodně (tamtéž), proto: jedna věc = jedno místo, ostatní jen odkazují.

### 6.4 Šablony

`docs/adr/0000-template.md`:
```
# NNNN: <rozhodnutí podstatným jménem>
Status: proposed | accepted | superseded by NNNN
## Context    — síly a fakta, bez hodnocení
## Decision   — „Budeme …“
## Consequences — pozitivní, negativní, neutrální
```
`modules/<m>/README.md`: *Účel (1 věta) · Veřejné API (`public.py`: funkce, DTO) · Eventy (vydává/poslouchá) · Tabulky (`<m>_*`) · Nastavení (`<M>_*`) · Závislosti na modulech*.

---

## 7. Škálování na statisíce uživatelů [D]

### 7.1 Co musí struktura umožnit

| Schopnost | Stav v TO [F] | Doporučení |
|---|---|---|
| Bezstavové procesy, horizontální škálování | `entrypoints/api.py` a `worker.py` (arq) oddělené. Session cookie `relace` | Žádný stav v paměti procesu mezi požadavky. Žádné sticky sessions, ty 12-factor zakazuje. Session, rate limit a cache v Redis/DB (rate limit už v `lib/rate_limit`) |
| Konfigurace přes env | pydantic-settings | §5. Velikosti poolů (`db_pool_size=2`) per proces v env, protože počet procesů × pool musí sedět na limit PG/pooleru |
| Logy | `lib/observability.py` | Strukturované logy na stdout jako proud událostí, směrování řeší platforma (12-factor, Logs). Korelační ID požadavku, metriky/trace (OpenTelemetry) zapojit v `lib/observability.py`, ne v modulech |
| Migrace | `database/migrations`, `target_guard.py` | Migrace jako samostatný krok vydání (job před nasazením), nikdy při startu API. Zpětně kompatibilní změny schématu (expand → contract) kvůli rolling deploy |
| Vyjmutelné moduly | tabulky s prefixem, „žádné JOINy do cizích“, eventy, `public.py` | Vyjmutelnost = modul nemá cizí tabulky, cizí ORM ani cizí `domain`. Komunikace přes `public.py` (sync) a eventy (async). Spring Modulith to definuje stejně: modul = poskytnuté API + interní implementace, cizí moduly smí jen na API |
| Těžká práce mimo request | arq worker, `opora_brain_pool_workers` | LLM a výpočty brain vždy přes frontu, request vrací stav nebo stream |
| Frontend | Vite SPA, `React.lazy` na routu (`frontend/CLAUDE.md`) | Code-splitting po `features/`. Statický build na CDN, API na stejném originu přes proxy |

### 7.2 Vynucení hranic nástrojem

- **Backend: import-linter.** Typy kontraktů: `forbidden`, `protected`, `layers`, `independence`, `acyclic_siblings` a vlastní (import-linter docs). `protected` a `independence` podporují wildcardy (`*`, `**`).
  **[D]** Nahradit 11 ručně psaných `forbidden` kontraktů:
  1. `layers` uvnitř modulu: `api` → `domain` ← `adapters` (doména nezná framework, to už je A7).
  2. Jeden kontrakt „mimo `public` nic“. Buď `protected` s `protected_modules = ["app.modules.*.domain", "app.modules.*.adapters", "app.modules.*.api"]`, nebo, pokud wildcard neumí výjimku „vlastní modul“, vlastní contract type (~30 řádků) nebo blok vygenerovaný skriptem ze seznamu modulů. **[?]** Jestli `protected` s wildcardem povolí importy uvnitř téhož modulu, jsem neověřil. Ověřit na větvi.
  3. `acyclic_siblings` nad `app.modules`.
- **Frontend: dependency-cruiser** (už je, „validate dependencies against rules“). Doplnit: `features/<a>` ↛ `features/<b>`, `shared` ↛ `features|pages|app`, zákaz `import.meta.env` mimo `shared/config/`. Alternativa je `eslint-plugin-boundaries` (typy elementů podle globů, výchozí `disallow`), ale TO používá oxlint, ne ESLint, takže zůstat u dependency-cruiseru.
- **Struktura:** `scripts/ci/check_paths.py` (§8.3) a kontrola velikosti souborů v `mise run architecture`.

### 7.3 Co NEdělat předčasně

- Mikroslužby, oddělená repa, Kubernetes, service mesh. Modulární monolit s hlídanými hranicemi je předpoklad pozdějšího vyjmutí, ne překážka.
- Monorepo orchestrátory (Nx, Turborepo): tři yarn workspaces a mise stačí.
- Event sourcing mimo existující append-only knihy (`credit_ledger`, události OPORA).
- src layout v Pythonu, barrel soubory, per-env konfigurační soubory v repu.
- GraphQL/BFF vrstva: proxy `/api` a OpenAPI stačí.

---

## 8. Plán migrace pro TO [D]

### 8.1 Mapování nejhorších oblastí

| Staré | Nové | Délka (nejhorší soubor) |
|---|---|---|
| `frontend/app/src/pages/oracle/components/prophet-two/components/<x>/` | `frontend/app/src/features/prophet-two/<x>/` (název domény sjednotit s backendem, např. `guided-process`: **rozhodne člověk**) | 109 → 83 |
| `…/prophet-two/{hooks,models,api}/` | `frontend/app/src/features/prophet-two/{hooks,model,api}/` | 96 → 70 |
| `…/pages/oracle/components/<ostatní 19>/` | `frontend/app/src/features/oracle/<x>/`. Sloučit varianty `prophet`, `prophet-secondary`, `prophet-window`, `prophet-window-controlled` podle významu | 96 → ≤ 78 |
| `frontend/app/src/pages/oracle/OraclePage.tsx` | beze změny (tenká stránka skládá `features/oracle` a `features/prophet-two`) | 44 |
| `'../../../../../lib/opory-api'` | `'@/shared/api/opory-api'` (`lib/` → `shared/lib`, `shared/api`) | – |
| `backend/app/modules/opora_brain/domain/kernel/<unit>/` | `backend/app/modules/kernel/domain/<unit>/` + `protected`: importuje jen `opora_brain` | 91 → 79 |
| `backend/app/modules/opora_brain/domain/seed_axes/{banka,derivace,uzel}.py` | `…/opora_brain/domain/seed_axes/{item_bank,derivation,node}.py` | – |
| `backend/app/modules/engine/domain/axes/dualita/jadro/` | `backend/app/modules/engine/domain/dualita/core/`. Přepočítat `JADRO.sha256` (`test_jadro_je_nedotcene.py` hlídá otisk) | 79 → 65 |
| `…/dualita/jadro/scenare/*_simulation.py` | `…/engine/domain/dualita/core/sims/` | 83 → 74 |
| `backend/app/modules/engine/domain/grid_projekce/` | `…/engine/domain/grid_projection/` | 77 → 78 |
| `.claude/workbench/axis-x/dualita/` + `tests/` | **smazat** (duplikát, ověřeno `cmp`) | – |
| `.claude/workbench/axis-x/funkce/osa-x/<skupina>/<fn>/{funkce.py,legenda,pasma,vahy,vystupy}.md` | `docs/reference/dualita/<fn>.md` (jeden soubor), `funkce.py` jen pokud nemá protějšek v `core/` | 76 → ≤ 40 |
| `.claude/workbench/{navrh,plan}-osa-X.md`, `.claude/infra/*.md` | `docs/explanation/dualita.md`, ADR | – |
| `tools/*` | `scripts/{dev,ci,…}/` | – |
| `docs/opora-workflow/**`, `docs/agent-system/**`, `docs/opora/**` | plátno OPORA / `docs/explanation/agent-system/` / `docs/explanation/` | – |
| `.env.example` ×4 | kořenový `.env.example` ×1 | – |
| `npm run be2:*`, `dev:be2` | `be:*`, venv přes mise (bez `.venv-app\Scripts`) | – |

### 8.2 Pořadí kroků (každý = jedna větev / PR, `git mv`, žádná změna chování)

0. **Základ:** `mise run check-full` zelený. Uložit počty testů: `pytest --collect-only -q | tail -1`, `vitest list | wc -l`.
1. **Brána délky** `scripts/ci/check_paths.py` v režimu ratchet (seznam výjimek = dnešních 45 cest > 90), zapojit do `mise run architecture`. Do `docs/how-to/windows-dev.md` přidat `git config core.longpaths true` a `LongPathsEnabled=1` (Microsoft). Obojí jako pojistka, ne jako řešení.
2. **Smazat `.claude/workbench`.** Katalog funkcí převést do `docs/reference/dualita/` (nebo do karet plátna). Ratchet se zmenší.
3. **Aliasy:** `paths: {"@/*": ["./src/*"]}` + `resolve.alias`/`resolve.tsconfigPaths` ve Vite a Vitest. `vite.config.js` → `.ts` (pravidlo „jen TS“). Codemod relativních importů. Ověřit `fe:typecheck` a `fe:arch`.
4. **`prophet-two` → `features/`.** Po něm zbytek `oracle`. Doplnit pravidla dependency-cruiseru pro `features/`.
5. **Backend:** kernel jako modul, `dualita/core`, anglické názvy. Upravit import-linter (generovaný blok), importy, `JADRO.sha256` a SPEC uzlů, které cesty citují.
6. **Konfigurace:** jeden `.env.example`, absolutní `env_file`, `<m>_settings.py` pro privacy/brain/sweep, test parity, proxy `/api`, odstranit `VITE_BACKEND*`.
7. **Dokumentace:** `docs/{tutorials,how-to,reference,explanation,adr}`, `pipeline/kontext/*` do gitu, `CLAUDE.md` → `@AGENTS.md`, `.claude/rules/`, kontrola mrtvých odkazů v CI. Výjimky ratchetu by v tu chvíli měly být prázdné.

### 8.3 Ověření

- **Chování:** `mise run check-full` (ruff, mypy, import-linter, pytest, oxlint, depcruise, tsc, vitest, migrace, bezpečnost) a stejný počet testů jako v kroku 0.
- **Historie:** `git diff -M --stat main...HEAD` ukazuje přejmenování (R100), ne smazání a přidání. `git log --follow` na vzorku.
- **Hranice:** `lint-imports` a `depcruise` bez výjimek navíc.
- **Délka cest** (načrt skriptu, rozpočet z R7):

```python
# scripts/ci/check_paths.py — ratchet: nové porušení = chyba, staré jen ve výjimkách
import re, subprocess, sys, pathlib
MAX_LEN, MAX_DEPTH = 100, 8
BANNED = [re.compile(r"components/[^/]+/components/"), re.compile(r"/domain/[^/]+/[^/]+/[^/]+/[^/]+$")]
allow = set(pathlib.Path("scripts/ci/path_exceptions.txt").read_text("utf-8").split())
files = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True).stdout.split("\n")
bad = [f for f in files if f and f not in allow and (
    len(f) > MAX_LEN or f.count("/") + 1 > MAX_DEPTH or any(p.search(f) for p in BANNED))]
stale = [a for a in allow if a not in files]           # výjimka, která už neexistuje = smazat ji
for f in bad: print(f"PATH {len(f):>3} {f}")
for a in stale: print(f"STALE exception {a}")
sys.exit(1 if bad or stale else 0)
```

- **Dokumenty:** skript, který v `*.md` a `CLAUDE.md` najde odkazy na cesty (`` `x/y` ``, `[..](..)`) a ověří jejich existenci. Dnes by našel aspoň 4 mrtvé (§2.4).

---

## 9. Zdroje

### Externí (primární)

- Microsoft, Maximum Path Length Limitation (MAX_PATH = 260 včetně NUL, `LongPathsEnabled`, manifest `longPathAware`): https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation
- Git for Windows, dlouhé cesty (`core.longpaths`, výchozí vypnuto, Explorer/cmd dál omezené, skriptované příkazy mohou selhat): https://gitforwindows.org/git-cannot-create-a-file-or-directory-with-a-long-path
- Feature-Sliced Design, přehled (vrstvy, slices, segments, import jen z nižší vrstvy): https://feature-sliced.design/docs/get-started/overview
- React, File Structure FAQ (3–4 úrovně vnoření, seskupení podle feature/route): https://legacy.reactjs.org/docs/faq-structure.html
- TypeScript, `paths` (nemění emitované importy): https://www.typescriptlang.org/tsconfig/#paths
- Vite, `resolve.alias` a `resolve.tsconfigPaths`: https://vite.dev/config/shared-options#resolve-alias
- Vite, Env Variables and Modes (`VITE_` ve veřejném bundlu, pořadí `.env*`, `ImportMetaEnv`): https://vite.dev/guide/env-and-mode
- Python Packaging, src layout vs flat layout: https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/
- FastAPI, Bigger Applications – Multiple Files: https://fastapi.tiangolo.com/tutorial/bigger-applications/
- The Twelve-Factor App, Config: https://12factor.net/config · Backing services: https://12factor.net/backing-services · Processes: https://12factor.net/processes · Logs: https://12factor.net/logs
- Pydantic Settings (priorita zdrojů, `env_file` relativně k CWD, `env_nested_delimiter`, `settings_customise_sources`): https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/
- Diátaxis: https://diataxis.fr/ · Reference: https://diataxis.fr/reference/
- Michael Nygard, Documenting Architecture Decisions (2011): https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions · ADR katalog: https://adr.github.io/
- Import Linter (typy kontraktů): https://import-linter.readthedocs.io/en/stable/ · Independence: https://import-linter.readthedocs.io/en/stable/contract_types/independence/ · Protected: https://import-linter.readthedocs.io/en/stable/contract_types/protected/
- Spring Modulith, Fundamentals (aplikační modul = poskytnuté API + interní implementace): https://docs.spring.io/spring-modulith/reference/fundamentals.html
- dependency-cruiser: https://github.com/sverweij/dependency-cruiser · eslint-plugin-boundaries: https://github.com/javierbrea/eslint-plugin-boundaries
- Claude Code, Memory (CLAUDE.md, `@path` importy, AGENTS.md, `.claude/rules/` s `paths`, < 200 řádků): https://code.claude.com/docs/en/memory

### Interní (cesty)

- TO: `CLAUDE.md`, `AGENTS.md`, `backend/CLAUDE.md`, `frontend/CLAUDE.md`, `backend/app/lib/config.py`, `.env.example`, `backend/.env.example`, `frontend/app/.env.example`, `frontend/app/{vite.config.js,tsconfig.json}`, `backend/pyproject.toml` (`[tool.importlinter]`), `package.json`, `mise.toml`, `.github/workflows/ci.yml`, `backend/app/main.py`, `.claude/workbench/axis-x/README.md`, `backend/app/modules/engine/domain/axes/dualita/jadro/`.
- AM: `CLAUDE.md`, `frontend/CLAUDE.md`, `backend/app/settings.py`, `.env.example`, `pyproject.toml`, `GLOSSARY.md`, `docs/adr/0001-backend-v2-python.md`.
- PL: `CLAUDE.md`, `docs/pravidla-struktury.md`, `docs/START-HERE.md`, `docs/README.md`, `frontend/STRUCTURE-PLAN.md`, `backend/STRUCTURE-PLAN.md`, `opora.toml`, `opora.local.toml`, `backend/app/factory.py`, `frontend/shared/project-capabilities/logic/project-capabilities.ts`, `frontend/app/components/App.tsx`, commit `71d4c2c`, `docs/navrhy/2026-10-14-vyvoj-tajemstvi-opory-v-platne.md`.

### Neověřeno

- [?] Jestli kontrakt `protected` v import-linteru s wildcardem povolí importy uvnitř téhož modulu. Rozhoduje, zda stačí jeden obecný kontrakt, nebo je potřeba vlastní typ či generátor.
- [?] Přesná sekce Pydantic o `TomlConfigSettingsSource` (načtená část stránky ji nepokryla). V doporučení se nepoužívá.
- [?] Výkon a limity Supabase pooleru při statisících uživatelů. Mimo rozsah, jen se upozorňuje na součin procesy × pool.
- [?] Jestli `pipeline/` (mimo git) obsahuje další zdroje pravdy, na které kód odkazuje. Spravovaný klon `pipeline/` nemá a pracovní kopie `P:\…\Tajemstvi-opory` se nečetla.
