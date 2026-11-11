# Zanořený pohled boxu (`box-focus`)

Plátno 2, Verze 5 (`docs/navrhy/2026-11-10-platno-2.md`): dvojklik na box layoutu (obě vrstvy) otevře místo layoutu stránky jeden box přes celou plochu plátna. Skládá ho `page-editor/components/PageEditor.tsx`; Detail boxu vpravo zůstává (`../../box-detail/`, bez vlastní skici, aby nad stejnou vrstvou neběžela dvě kreslení).

- **Drobečky** Stránka › Box › vnořený box: klik na předka zanoří tam, na stránku nebo **← Zpět na layout** vrátí layout. **Esc** (mimo kreslení, pole a otevřená okna) vrátí o úroveň výš.
- **Vlevo vnořené boxy**: klik vybere box do Detailu, dvojklik (nebo Enter) zanoří dál.
- **Uprostřed kresba skici** boxu: existující `editor/canvas/drawing/` `DrawingWorkspace` (líně načtený) nad vrstvou `box/<pageId>/<sectionId>`; ukládá samo kreslení. **🖼 Vložit inspiraci do kresby** vloží obrázky inspirace boxu (`section.inspiration.files`, už nahrané v `/api/drawing-files`) jako obrázky Excalidraw s `fileId` vpravo vedle kresby; ty, které v kresbě už jsou, znovu nevloží.
- **Zámek obsahu** (Git main, kompletní stránka; `lockText.drawing` = bez přechodných stavů ukládání): místo kreslení věta proč a náhled uložené skici.
- **Adresa**: otevřený box je v `boxId` (`logic/use-box-focus.ts`), přežije obnovení i návrat z plátna logiky; změna stránky ho zruší, neznámý box = layout. App ho při přepisu adresy zachová.

Soubory: `components/BoxFocus.tsx`, `components/BoxFocusSketch.tsx`, `logic/box-focus.ts` (test vedle: `focusPath`, `withBoxParam`, `notInScene`, `besideScene`, `inspirationSkeletons`), `logic/use-box-focus.ts`, `styles/box-focus.css` (předpona `box-focus`).
