Katalog Knihovny jako **data**. Panel `frontend/layout/library-navbar/`, tlačítko Vložit i přetažení berou obsah odsud. Prvky jsou seskupené pod Frontend, Backend, Databáze a Infrastruktura; původní jemné kategorie a ID zůstávají. Kontrakt: `docs/menu-a-katalog.md` §B.

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

Přetažení nebo Vložit vytvoří novou komponentu se specifikací. Puštění na uzel/sektor ji vloží jako potomka, puštění na oblast ji geometricky umístí dovnitř. Blok do existující karty se přidává jen výslovnou akcí z detailu prvku. Struktura v Knihovně je jediný strom již vložených instancí; není kopií katalogu.

## Co se zapíše na plátno (`catalog-plan.ts`, blok přes `catalog-insert.ts`)

| Pole | Nová komponenta | Výslovné přidání bloku do vybrané karty |
|---|---|---|
| `label` | `node.name` | `block.title` |
| `purpose` | `node.purpose` a výchozí `spec.goal` | první odstavec textu |
| `relates` | oddíl „Souvisí s“ v uloženém textu karty | odstavec „Souvisí s:“ |
| `done` | `spec.acceptance`, bez duplicitního checklistu | odstavec „Hotovo, když:“ |
| `invariants` | pravidla omezená na novou kartu | přidají se do `rules` karty, stejný text se přeskočí |
| `steps` | oddíl kroků v uloženém textu karty | odstavec „Kroky:“ |
| `template` | oddíl „Šablona“ v uloženém textu karty | konec textu |
| `category` | — | `block.tags` |

Nová instance jde přes jednu dávku `canvas-plan`, která uloží graf, specifikaci a obsah. `node-brief` vydá modelu `node.purpose`, `goal.goal`, `definitionOfDone.acceptance`, pravidla v `boundaries` a uložený text karty. Nové předlohy nezakládají rozbalené pracovní bloky: plátno zůstává kompaktní, celý podklad je v detailu a předávce. Uložené karty ze staršího tvaru katalogu včetně checklistů a bloků se načtou beze změny; změna předlohy je zpětně nepřepisuje. Starší čisté převody `cardFromItem` a `workflowFromItem` zůstávají kompatibilními pomocníky, nikoli cestou nového UI vložení.

## Soubory v `logic/`

- `library-catalog.ts` — typy, kategorie, složený `CATALOG_ITEMS` a čisté funkce: `itemsOf`, `itemById`, `searchItems` (popisek + účel, bez diakritiky), `foldDiacritics`, `relatesRef`, `relatesLines`, `catalogLint`, konstanta `CATALOG_DRAG_TYPE`.
- `catalog-practical.ts` — praktické předlohy tlačítka, dialogu, parallax animace, endpointu, datové tabulky a dalších částí aplikace; `catalog-families.ts` — čtyři hlavní skupiny a mapování vrstvy karty.
- `catalog-plan.ts` — společné umístění a dávka pro Vložit i přetažení; uloží specifikaci, text a pravidla nové komponenty.
- `catalog-frontend-components.ts`, `catalog-frontend-style.ts`, `catalog-frontend-logic.ts`, `catalog-backend.ts` (backend + databáze), `catalog-platform.ts` (cloud + cache), `catalog-safety.ts` (security + testy), `catalog-architecture.ts` (Multitenance a prvky pro jednu architekturu) — jen data.
- `catalog-insert.ts` — `cardFromItem`, `workflowFromItem`, `blockTextFromItem`, `blockFromItem`, `rulesFromItem`, `criteriaFromItem`, `insertBlockFromItem`, konstanty `RELATES_BLOCK_TITLE` a `TEMPLATE_BLOCK_TITLE`.
- `catalog-fit.ts` — `fitsProfile`, `splitByProfile`, `fitReason`, `fitWords`, `outsideSummary`; používá ji i katalog Agentů.
- Testy vedle: `library-catalog.test.ts`, `catalog-lint.test.ts` (trvalá brána `catalogLint(CATALOG_ITEMS) == []`), `catalog-insert.test.ts`, `catalog-fit.test.ts`.

## Lint (`catalogLint`)

- Tvar prvku: neprázdný `purpose`, 1–3 `done`, nejvýš 2 `invariants`, každé `@id` v `relates` míří na existující prvek a ne na sebe.
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
