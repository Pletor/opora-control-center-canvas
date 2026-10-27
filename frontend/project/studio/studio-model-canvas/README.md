# Studio · MODEL · plátno

Plátno vrstvy MODEL (`docs/studio.md` §1, §3, §4; etapa S6a). Design karet, portů a propojování z vlastního prototypu
`04.Architektura-projektu/prototype` (`component-visuals.mjs`, `ports.mjs`, `connection-gesture.mjs`, `reference-theme.css`).

- `components/StudioModelCanvas.tsx` – React Flow plátno: karty modelu, tah karty (poloha do modelu po puštění, vazby jdou
  s kartou už během tahu), puštění typu z katalogu, výběr karty i vazby, zoom 0,1–3, fit, minimapa, trvalý štítek
  „MODEL – výpočet, ne měření“ a fialovější tón pozadí (`--studio-model-*`). Všechny změny hlásí rodiči.
- `components/ModelCard.tsx`, `ModelPort.tsx` – karta podle typu (ikona, název, typ, tři stupně fungování, vazba na kartu
  OPORY se skutečným stavem) a port na obvodu. `components/ModelLinks.tsx` – vazby v souřadnicích plátna
  (`ViewportPortal`, pod kartami) a náhled tažené vazby.
- `logic/model-flow.ts` – rozměry karet (`cardGeometry`), strany portů a trasy vazeb (`layoutStudioConnections`), pohled
  karet, vazeb a uzly React Flow. `logic/connect-gesture.ts` – klik port → port, orientace výstup → vstup, kompatibilní
  a ztlumené cíle (`connectionError`). `logic/use-connect-drag.ts` – tah vazby s náhledem (Escape ruší).
  `logic/card-actions.ts` – kontext akcí portu. `logic/card-stages.ts` – tři stupně fungování podle typu (data).
- `styles/studio-model-canvas.css`, blok `studio-model-canvas`.
