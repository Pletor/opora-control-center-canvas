# R01 — trvalé zadání uzlu

STATUS: READY
Autor: Astra v Hermesu. Uživatel schválil tento postup 2026-09-09 po neúspěšném Fable volání (401); nejde o Fable schválení.

## Výsledek
U vybraného uzlu člověk edituje goal, non_goals a acceptance. Uložené zadání přežije restart a dvě okna jej nemohou tiše přepsat. Rozpracovaný text zůstane při chybě a při přepnutí uzlu. Existující purpose a graph JSON zůstávají kompatibilní.

## Data a autorita
Samostatná SQLite historie keyed project/workspace/node/revision; nejnovější úspěšná revize je aktuální záznam. Revision 0 znamená chybějící lokální zadání, ne schválenou specifikaci. GET nemutuje. POST s expected_revision přes atomický CAS. Pole jsou přesně goal/non_goals/acceptance: str, max 4000/8000/12000 znaků, bez NUL. Revision musí být int >=0, nikoli bool. Neznámá pole odmítnout.
Draft/draft a validní managed workspace jsou editovatelné, existenci uzlu a vlastnictví projektu ověřit pro každé read/write. Main je read-only; Git import zadání není implementován, proto main ukazuje explicitní nedostupnost. Workspace zadání je lokální editorový záznam, není součástí Git commitů. Přenos do Git je NEXT NODE.

## Rozhraní
GET /api/node-spec?project=&workspace=&node= → fields, revision, readOnly, available, source.
POST /api/node-spec JSON {project,workspace,node,expected_revision,fields} → uložená verze.
GET /api/node-spec/history se stejným scope → posledních max 20 revizí + has_more; žádné neomezené výpisy.
Origin/body limit zůstávají. Chyby neprozrazují tajemství. Uložení atomické přes SQLite transakci a serialization vůči graph změnám. Souběžné instance DB vynucují compare-and-swap.

## UI
Samostatný NodeSpecEditor v NodePanel, binding project/workspace/node. Cíl, Co není součástí a Podmínky dokončení. Loading/saving/dirty/saved/error/conflict. Tlačítko Uložit zadání; pole disabled pouze při načítání/save nebo main. Scope-keyed paměť rozepsaného textu v rámci otevřené aplikace; není garantováno přežití neuloženého textu při úplném reloadu, UI to přizná. Chybové odpovědi i pozdní výsledky nesmějí zahodit místní text nebo měnit jiný scope.

## Scope
backend/node_specs.py, backend/service.py, backend/app.py; src/NodeSpecEditor.tsx, src/NodePanel.tsx, src/App.tsx, src/types.ts, existující CSS; tests/test_node_specs.py a e2e/node-spec.spec.ts. Testovací port izolovat přes OPORA_CANVAS_PORT (default8740) a playwright.config.ts (8741) s negativním Host testem. Jen tento WorkUnit a jeho důkazy, žádné cizí repo změny.

## Akceptace
RED→GREEN persistence API, CAS konflikt a historie, validation/scope/main guard, reálný UI save/reload, přepnutí uzlu a dva klienti, pozdní async response. Full pytest, Ruff, TypeScript/Vite, Playwright bez produkčních fixture writes. Nezávislé review exact změn. Jediný writer v .worktrees/R01 uvnitř primárního kořene. Main aktualizovat až po gate.

## Non-goals
Žádný runtime LLM tunel, kontext compiler, import codebase, Excalidraw, automatická paměť, voice, push/merge externího repo ani další rewrite. Produkční data a historické podklady se nemažou.
