# Plátno Studia

`components/StudioCanvas.tsx` vykreslí jednu úroveň v React Flow: tečkovaná mřížka 24 px, karty na deterministických polohách, minimapa vpravo dole (karty v barvě stavu), ovladače ± a fit vpravo nahoře, zoom 0,1–3. Karty se netahají, polohy se neukládají. Klik vybere, dvojklik nebo Enter sestoupí, Backspace vystoupí, šipky posunou výběr, Escape výběr zruší; vše jde callbacky rodiči.

- `components/StudioLink.tsx` – souhrnná vazba: Bézierova křivka podle normály portu, barva a čára podle `carries` (`docs/zive-zobrazeni-a-knihovna.md` §2), tooltip s druhem a počtem, štítek s počtem u vazby z více hran.
- `logic/studio-layout.ts` – vrstvy zleva doprava podle směru vazeb (nejdelší cesta), řádky v pořadí grafu, skupina „bez sekce“ pod hlavním blokem v rámu.
- `logic/studio-bezier.ts` – ohyb z prototypu (`routing.mjs`): vzdálenost × 0,35, 20–140 px.
- `logic/studio-keys.ts` – klávesy a nejbližší karta ve směru.
- `logic/canvas-flow.ts` – uzly a hrany React Flow; uzly nesou pevné rozměry, protože plátno je řízené bez `onNodesChange` (jinak minimapa karty nevidí).
- `styles/studio-canvas.css`, blok `studio-canvas`.
