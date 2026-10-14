# project-map

Lehká mapa kódu v prostředí Projekt. Místo původního Graphify HTML (vis-network, stovky uzlů a „Community N“)
ukazuje oblasti projektu jako bubliny pojmenované podle společné složky. Data dává `GET /api/graphify/overview?project=`
(`backend/project/maps/graphify_overview.py`), které čte jen `graphify-out/graph.json`.

- `components/ProjectMap.tsx` — rodič: načte přehled, drží výběr, hledání a pohled (viewBox) a skládá dílky.
  Při 404 zavolá `onMissing` (rodič spustí Graphify), po načtení hlásí `onLoaded` (počty do popisku).
- `components/MapCanvas.tsx` — SVG plátno: bubliny (velikost = počet uzlů, číslo uvnitř), čáry vazeb, kolečko = zoom
  kolem kurzoru, tah = posun, klik = výběr. Vybraná oblast a její vazby svítí, ostatní vazby ustoupí.
- `components/MapSidebar.tsx` — hledání, seznam oblastí podle velikosti a detail vybrané (nejpropojenější soubory
  se stupněm a cestou, sousední oblasti s vahou; klik přeskočí).
- `components/MapLegend.tsx` — jak číst velikost, čáru a barvu.
- `logic/project-map-model.ts` — typy odpovědi a čisté funkce: `layoutCommunities` (deterministická spirála bez
  překryvů), `edgeLines` (nejsilnější vazby, tloušťka log), `filterCommunities`, `communityColor`/`communityTone`
  (cyklus přes `--cat-*`), `neighbors`, `fitView`, `zoomAt`, `panBy`, `shortLabel`. Test vedle.
- `styles/project-map.css` — bloky `project-map`, `project-map-canvas`, `project-map-sidebar`, `project-map-legend`.
  Stav a chyba používají `archify-status` a `archify-error` z `../styles/archify-map.css`.

Původní HTML zůstává za tlačítkem „Původní Graphify HTML“ v `GraphifyMap.tsx` a načte se až na kliknutí.
