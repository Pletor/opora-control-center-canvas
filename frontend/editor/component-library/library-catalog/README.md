Katalog Knihovny jako **data**. Katalog v prostředí Projekt (`frontend/project/architecture-editor/page-editor/`) a jeho přetažení berou obsah odsud (panel Knihovny v Editoru je smazaný). Prvky jsou seskupené pod Frontend, Backend, Databáze a Infrastruktura; původní jemné kategorie a ID zůstávají. Kontrakt: `docs/menu-a-katalog.md` §B.

Prvek je know-how pro silný model. Neříká, jak dělat dobrou práci; říká, k čemu prvek je, s čím v projektu souvisí, kdy je hotovo a kterou hranici nesmí překročit.

## Tvar prvku (`CatalogItem`)

- `id` — stabilní identita; jde v tažení přes `dataTransfer` a vrací se přes `itemById(id)`.
- `category` — jedna z deseti kategorií (`CatalogCategory`): `fe-components`, `fe-css`, `fe-logic`, `backend`, `database`, `tenancy`, `cloud`, `cache`, `security`, `tests`.
- `label` — název v panelu.
- `purpose` — k čemu prvek je, jedna věta.
- `relates` — s čím souvisí: `@id` jiného prvku Knihovny, nebo krátká věta o vrstvě či datech. `relatesLines` přeloží `@id` na „Název: účel“.
- `done` — 1–3 ověřitelná kritéria hotovo.
- `invariants` — 0–2 skutečné tvrdé hranice `{ text, kind: "must" | "must_not" }`. Jen to, co při porušení rozbije bezpečnost, data nebo kontrakt. Obecné rady („přidej testy“, „čistý kód“) sem nepatří.
- `steps?` — kroky rozpadu, jen když nesou informaci navíc.
- `template?` — kostra kódu v konvencích repozitáře.
- `fits?` — pro které projekty prvek dává smysl (`docs/suplik-a-profil.md`); bez `fits` patří všem.

Kontext pro agenta (`docs/zive-zobrazeni-a-knihovna.md` §5, tvar a lint v `catalog-agent-context.ts`), vše volitelné:

- `tech?` — 1–80 znaků, předvyplní `card.tech`.
- `states?` — 1–8 různých stavů po 1–40 znacích, předvyplní `card.states`. Položka s výstupním portem `carries: "command"` musí mít stav chyby (`chyba` / `error` / `selhání`, jako `ERROR_STATES` kontroly mapy).
- `ports?` — `[{ id, direction: "in" | "out", carries }]`, `id` `[A-Za-z0-9_-]{1,40}` unikátní v položce, nejvýš 8, `carries` ∈ `navigation | data | command | event`.
- `fetch?` — `{ files: [], docs: [] }`: relativní cesty v **tomto repozitáři** (u `docs` i `https://`), nejvýš 20 v seznamu. Katalog je statický soubor, k souborům má přístup jen vitest, proto existenci ověřuje brána v `catalog-lint.test.ts` (`catalogLint(items, exists)`).
- `fill?` — pole karty, která má agent vyplnit, jen z `CARD_FILL_FIELDS`: `purpose`, `sourceRef`, `spec.goal`, `spec.non_goals`, `spec.acceptance`, `spec.steps`, `text`, `card.tech`, `card.states`, `card.section`, `blocks`, `rules` (to, co agent umí zapsat změnou grafu, `extend` dávky plánu nebo návrhem změny zadání u `spec.steps`). `spec.steps` = „navrhni kartě kroky plánu“ a smí ho mít jen položka s porty (s logikou); mají ho Formulář s validací, Router a modul prostředí a API endpoint. Seznam zrcadlí `backend/canvas/card_agent_context.py`, shodu hlídá `catalog-agent-context.test.ts`.

Přetažení nebo Vložit vytvoří novou komponentu se specifikací. Puštění na uzel/sektor ji vloží jako potomka, puštění na oblast ji geometricky umístí dovnitř. Strom již vložených instancí je sekce Struktura v menu Editoru; není kopií katalogu.

## Co se zapíše na plátno (`catalog-plan.ts`)

| Pole | Nová komponenta |
|---|---|
| `label` | `node.name` |
| `purpose` | `node.purpose` a výchozí `spec.goal` |
| `relates` | oddíl „Souvisí s“ v uloženém textu karty |
| `done` | `spec.acceptance`, bez duplicitního checklistu |
| `invariants` | pravidla omezená na novou kartu |
| `steps` | oddíl kroků v uloženém textu karty |
| `template` | oddíl „Šablona“ v uloženém textu karty |
| `tech`, `states` | `card.tech`, `card.states` |
| `fetch`, `fill` | `card.fetch` (prázdný seznam se vynechá), `card.fill`; node-brief je vydá v `node` mimo zadání |
| `ports` | oddíl „Porty“ v uloženém textu karty; při cíleném vložení (`CatalogLink`) navíc jedna vazba `next` s `carries` prvního portu daného směru |
| `category` | — |

Nová instance jde přes jednu dávku `canvas-plan`, která uloží graf, specifikaci a obsah. `node-brief` vydá modelu `node.purpose`, `goal.goal`, `definitionOfDone.acceptance`, pravidla v `boundaries` a uložený text karty. Nové předlohy nezakládají rozbalené pracovní bloky: plátno zůstává kompaktní, celý podklad je v detailu a předávce. Uložené karty ze staršího tvaru katalogu včetně checklistů a bloků se načtou beze změny; změna předlohy je zpětně nepřepisuje.

## Soubory v `logic/`

- `library-catalog.ts` — typy, kategorie, složený `CATALOG_ITEMS` a čisté funkce: `itemsOf`, `itemById`, `searchItems` (popisek + účel, bez diakritiky), `foldDiacritics`, `relatesRef`, `relatesLines`, `catalogLint`, konstanta `CATALOG_DRAG_TYPE`.
- `catalog-practical.ts` — praktické předlohy tlačítka, dialogu, parallax animace, endpointu, datové tabulky a dalších částí aplikace; `catalog-families.ts` — čtyři hlavní skupiny a mapování vrstvy karty.
- `catalog-plan.ts` — společné umístění a dávka pro Vložit i přetažení; uloží specifikaci, text, pravidla a kontext pro agenta nové komponenty (`catalogCardContext`) a u cíleného vložení navrženou vazbu (`catalogEdges`). Vložení je deterministické, bez modelu.
- `catalog-agent-context.ts` — typy `CatalogPort`, `CatalogFetch`, seznam `CARD_FILL_FIELDS`, `ERROR_STATES` a lint `agentContextViolations` (volá ho `catalogLint`).
- `catalog-frontend-components.ts`, `catalog-frontend-style.ts`, `catalog-frontend-logic.ts`, `catalog-backend.ts` (backend + databáze), `catalog-platform.ts` (cloud + cache), `catalog-safety.ts` (security + testy), `catalog-architecture.ts` (Multitenance a prvky pro jednu architekturu) — jen data.
- `catalog-fit.ts` — typ `CatalogFit` pole `fits` a funkce `fitsProfile`, `splitByProfile`, `fitReason`, `fitWords`, `outsideSummary`; filtr profilu v UI dnes nikdo nevolá (šuplík Knihovny/Agentů je smazaný), test hlídá platnost `fits` v datech.
- Testy vedle: `library-catalog.test.ts`, `catalog-lint.test.ts` (trvalá brána `catalogLint(CATALOG_ITEMS) == []` a existence souborů `fetch`), `catalog-agent-context.test.ts`, `catalog-plan.test.ts`, `catalog-fit.test.ts`.

## Lint (`catalogLint`)

- Tvar prvku: neprázdný `purpose`, 1–3 `done`, nejvýš 2 `invariants`, každé `@id` v `relates` míří na existující prvek a ne na sebe.
- Kontext pro agenta: `tech`, `states`, `ports`, `fetch`, `fill` podle tvaru výše (pravidla `tech` / `states` / `ports` / `fetch` / `fill`).
- Šablony stylů: `px` jen na `border*` (kromě `border-radius`), `outline*`, `box-shadow` / `text-shadow`, na 1px lince a na ikoně do 24; selektory se nevnoří přes tři úrovně; žádné `!important`, `#id` ani `blok__prvek__prvek`.

## Sloučené duplicity (2026-10-01)

Zůstalo první id, druhé zaniklo. Obsah zaniklého prvku je v ponechaném prvku (kroky, hotovo, invarianty) nebo v `relates`.

| Ponechaný prvek | Zaniklý prvek | Proč |
|---|---|---|
| `fe-form-validated` | `fe-form-state-split` | Rozepsaná hodnota v poli a hotová nahoru je jádro formuláře. |
| `fe-auth-guard` | `fe-member-area` | Členská sekce i guard popisovaly tutéž relaci, guard a server. |
| `sec-server-validation` | `be-input-validation` | Validace na serveru byla dvakrát (backend a security). |
| `sec-no-secrets` | `cloud-env-vars` | `.env.example` a tajemství mimo git jsou jedno pravidlo. |
| `cloud-env-split` | `cloud-single-source-ports` | Port a cesty z jednoho místa jsou součást konfigurace prostředí. |
| `be-environment-router` | `be-module-with-test` | Router a modul prostředí s testem vedle jsou jedno pravidlo z CLAUDE.md. |
| `cache-digest-key` | `cache-invalidate-on-source` | Klíč z otisku vstupů je sám invalidace při změně zdroje. |

Opakovaný obsah, který zůstal jen na jednom místě:

- „Test vedle modulu“ žije jen v `test-unit-beside`; `fe-pure-model`, `be-environment-router` a další na něj odkazují.
- Tři brány hotovo (`uv run pytest backend`, `npm test`, `npm run build`) žijí jen v `test-done-gates`; `cloud-repeatable-build` na něj odkazuje a šablonu s branami už nemá.
- Architektonická pravidla z Agentů jsou invarianty prvků: `rule-tenant-in-every-query` → `tenant-request-context` a `tenant-data-isolation`, `rule-modules-keep-data` → `be-module-boundary`, `rule-service-owns-data` → `ms-service-database`.

Katalog nezná projekt: nečte `sourceKind`, id projektu ani pracovní prostor. Je stejný pro všechny projekty.
