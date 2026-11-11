# Kontext prvku na plátně toku (`element-context`)

Plátno logiky prvku plátna 2 (`docs/navrhy/2026-11-10-platno-2.md`, verze 4): tok projektu s `owner_ref = opora:project-flow:<nodeId>`, jehož uzel je prvek logiky (`element`). Hlavička `LibraryCanvas` místo „knihovna“ ukáže, čí logika to je, a vrátí člověka na plán stránky. Editor, verze, kontrola grafu a příkazový řádek se nemění.

- `components/ElementContextHead.tsx` — **← Zpět na plán stránky**, druh a název prvku, stránka › box (bez boxu „celá stránka“). Návrat jen hlásí nahoru.
- `logic/element-context.ts` — `elementContext(graph, nodeId)`: druh (`logicLook`), název, stránka (rodič prvku), box (`card.section` v `site.sections`) a doména; jiný uzel = `null`. `planRoute(search, context)`: adresa návratu (`projectView=architecture`, `domainId`, `pageId`, `architectureNode`, bez staré `editorId` a `flow`). Test `element-context.test.ts`.
- Titulek plátna `logicCanvasTitle` = „Logika a tok dat · <prvek>“ a výzva prázdného plátna `LOGIC_PROMPT` (vstupy → kroky → výstupy, podmínky) pro `command-bar/EmptyPrompt` (`title`, `lead`), obojí v `element-context.ts`.
- `logic/use-element-context.ts` — jen u plátna tohoto projektu načte graf prostoru (`/api/view`); chyba = žádný kontext, hlavička zůstane obecná.
- `styles/element-context.css`, blok `element-context`.

Rodič (`LibraryCanvas`) při návratu přepíše adresu `planRoute` a zavolá `onBack`; editor architektury si doménu, stránku a vybraný prvek přečte z adresy. Návrat se odvozuje z grafu, takže funguje i u plátna otevřeného přímým odkazem.
