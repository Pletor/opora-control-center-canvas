Katalog Agentů a Postupů (JAK pracovat s modely) jako **data**. Sdílí jazyk s Knihovnou
(`frontend/editor/component-library/library-catalog/`): `purpose`, `relates`, `invariants`, `steps`,
`done` a funkce `relatesLines` / `foldDiacritics` se odtud **importují, ne kopírují**. Panel
`frontend/layout/agent-navbar/` a puštění na plátno (`agent-insert.ts`) berou obsah odsud. Kontrakt:
`docs/menu-a-katalog.md` §B3.

## Tvar položky (`AgentItem`)

- `id` — stabilní identita; jde v tažení pod typem `AGENT_DRAG_TYPE` a vrací se přes `agentItemById(id)`.
  Id pipeline a hooků jsou uložená v `actions[].pipelineId` na kartách, proto se nemění.
- `category` — `workflows`, `pipelines`, `agents`, `skills`, `hooks`, `rules`. Kategorie `rules` je od §B3
  **Hranice**: id zůstalo kvůli uloženým preferencím panelu a mapování ikon.
- `label`, `purpose` — název a k čemu položka je.
- `kind` — co puštění vytvoří: `rule` (Hranice) a `agent` → pravidla karty, `action` (pipeline, hook) →
  akce v bloku Akce, `workflow` → sektor s kartami fází, `info` (skill) → netáhne se.
- `relates` — `@id` položky Agentů nebo prvku Knihovny, nebo krátká věta. `agentRelatesLines` je přeloží.
- `invariants` — 0–2 tvrdé hranice; na kartě se z nich stanou pravidla.
- `steps`, `done`, `stopCondition` — povinné u workflow a pipeline. Kroky workflow mají názvy fází
  `discover`, `define`, `build`, `verify`, `live`.
- `fits?` — jako v Knihovně.

## Co puštění na plátno udělá (`agent-insert.ts`)

Board pošle `onAgentDrop(itemId, x, y, targetId)`; `targetId` je karta pod ukazatelem. App vloží do
ní, jinak do vybrané karty; bez obojího jen řekne, co chybí. Do uzavřené karty nevkládá nic.

| `kind` | Kam | Co vznikne |
|---|---|---|
| `rule` | pravidla karty | `ruleFromItem`: invarianty jako `must` / `must_not` beze změny textu. |
| `agent` | pravidla karty | navíc první `must` „Role: `<label>`. `<purpose>`“. |
| `action` | blok Akce | `actionFromItem`: `pipelineId` = id položky, parametry `purpose`, `steps`, `done`, `stopCondition`, `relates` jako texty (prázdné se vynechají). |
| `workflow` | graf | `sectorFromWorkflow`: sektor s účelem, invariantami jako pravidly a blokem „Souvisí s“; uvnitř karta na každou fázi z kroků, vazby `next`, kritéria hotovo na poslední kartě. Stop podmínka nemá na kartě pole a zůstává v katalogu. |
| `info` | nikam | všechny překlady vrací `null`. |

Stejné pravidlo (podle textu) ani tatáž pipeline (podle `pipelineId`) se nepřidají dvakrát.

## Lint (`agentCatalogLint`)

| `rule` | Kdy se ohlásí |
|---|---|
| `purpose` | Prázdný účel. |
| `invariants` | Víc než 2 invarianty. |
| `done` / `stop` / `steps` | Workflow nebo pipeline bez 1–3 kritérií hotovo, stop podmínky nebo kroků. |
| `phases` | Kroky workflow nepojmenují všech pět fází. |
| `ref` | `@id` neexistuje (v Agentech ani v Knihovně), odkazuje sám na sebe, nebo pipeline neodkazuje na žádný prvek Knihovny. |

## Rozpuštěná kategorie Pravidla (2026-10-01)

| Bývalé pravidlo | Kam |
|---|---|
| `rule-no-model-launch`, `rule-materials-not-commands`, `rule-no-delete-without-preview` | zůstala jako kategorie **Hranice** |
| `rule-tenant-in-every-query` | invarianty `tenant-request-context` a `tenant-data-isolation` (Knihovna) |
| `rule-modules-keep-data` | invarianty `be-module-boundary` (Knihovna) |
| `rule-service-owns-data` | invarianta `ms-service-database` (Knihovna) |
| `rule-no-secrets` | smazáno, duplikovalo `sec-no-secrets` |
| `rule-tests-before-done-workspace` | smazáno, duplikovalo `test-done-gates` a `pl-fill-card-via-api` |
| `rule-no-deps-without-consent` | smazáno, obecné chování agenta |

Další sloučené položky: `hook-verify-gates` (= `pl-verify-before-done` a `test-done-gates`),
`hook-pre-save-lock` (= `be-cas-revision`) a `skill-selection-general` (obecná rada) zanikly. Na uložených
kartách zůstává jejich `pipelineId` jako text; nic ho nedohledává, takže se karty načtou beze změny.

## Soubory v `logic/`

- `agent-catalog.ts` — typy, kategorie, `AGENT_ITEMS`, `agentItemsOf`, `agentItemById`, `relatedInfo`,
  `agentRelatesLines`, `searchAgentItems`, `agentCatalogLint`, `startAgentDrag`, `AGENT_DRAG_TYPE`.
- `catalog-workflows.ts`, `catalog-pipelines.ts`, `catalog-agents.ts`, `catalog-skills.ts`,
  `catalog-hooks.ts`, `catalog-boundaries.ts` — jen data, po kategorii na soubor.
- `agent-insert.ts` — `ruleFromItem`, `actionFromItem`, `sectorFromWorkflow`, `insertRulesFromItem`,
  `insertActionFromItem`, `phasesFromSteps`, `phaseNote`, `PHASE_LABELS`, `PHASE_ORIGIN`, `PHASE_STEP`,
  `NEW_CARD_PHASE`.
- Testy vedle: `agent-catalog.test.ts`, `agent-insert.test.ts`.

Katalog nezná projekt: nečte `sourceKind`, id projektu ani pracovní prostor.
