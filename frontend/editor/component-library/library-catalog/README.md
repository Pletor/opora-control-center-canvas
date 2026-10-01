Katalog Knihovny jako **data**. Prvek mimo katalog neexistuje: panel `frontend/layout/library-navbar/` i puštění na plátno berou obsah odsud a nic si nedomýšlejí. Kontrakt: `docs/menu-a-katalog.md` §B.

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

Prvek **nemá druh** karta/blok. Co z něj vznikne, určí místo puštění.

## Co se zapíše na plátno (`catalog-insert.ts`)

| Pole | Nová karta (prázdné plátno) | Blok do karty pod ukazatelem |
|---|---|---|
| `label` | `node.name` | `block.title` |
| `purpose` | `node.purpose` | první odstavec textu |
| `relates` | první blok „Souvisí s“ (řádky) | odstavec „Souvisí s:“ |
| `done` | `criteria` karty | odstavec „Hotovo, když:“ |
| `invariants` | `rules` karty | přidají se do `rules` karty, stejný text se přeskočí |
| `steps` | bloky | odstavec „Kroky:“ |
| `template` | blok „Šablona“ | konec textu |
| `category` | — | `block.tags` |

`node-brief` z toho vydá modelu `node.purpose`, `definitionOfDone.criteria`, `boundaries.nodeRules` a blok „Souvisí s“ bez zásahu do backendu. Uložené karty ze staršího tvaru katalogu mají stejný tvar dat, proto se načtou beze změny.

## Soubory v `logic/`

- `library-catalog.ts` — typy, kategorie, složený `CATALOG_ITEMS` a čisté funkce: `itemsOf`, `itemById`, `searchItems` (popisek + účel, bez diakritiky), `foldDiacritics`, `relatesRef`, `relatesLines`, `catalogLint`, konstanta `CATALOG_DRAG_TYPE`.
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
