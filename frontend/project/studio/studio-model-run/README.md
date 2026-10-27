# Studio · MODEL · běh

Běh simulace vrstvy MODEL (`docs/studio.md` §5, etapa S6b), načtený líně s celým MODELem. Chování a časování z prototypu
`04.Architektura-projektu/prototype` (`app.mjs` RUN lišta a smyčka ticku, `animations.mjs` částice). Běh počítá jen
v prohlížeči nad aktuálním (i neuloženým) modelem a nic neukládá; čísla jsou výpočet modelu, nikdy měření a nikdy
zápis do karet OPORY ani do `/api/graph`.

- `components/ModelRunBar.tsx` – lišta RUN: Start / Pause, +1 krok, rychlost 0,25–5× (výchozí 1×), čítač ticku, Reset,
  Surge ×5, Obnovit vše, Scénáře a souhrn (propustnost, chybovost, nejvytíženější komponenta) se štítkem „výpočet modelu“.
- `components/ModelLinkFlow.tsx` – částice jedné vazby (vykresluje `ModelLinks` plátna), polohu píše animátor.
- `logic/run-control.ts` – stav běhu, krok (`stepSimulation`), incident hned do běhu (příkaz + náhled bez posunu času),
  reset, rychlost → prodleva, otisk modelu pro reset po editaci.
- `logic/use-model-run.ts` – hook rodiče: smyčka ticku (`setTimeout` řetěz), kontrola modelu před startem, reset s hláškou,
  když se změní, co engine počítá (typy, konfigurace, vazby); poloha, název a plán incidentů běh nechají.
- `logic/run-history.ts` – posledních 60 ticků uzlů, vazeb a souhrnu (jen vykonané kroky).
- `logic/run-view.ts` – stav simulace → karty (stav, tři čísla stupňů, propustnost, využití, latence, chyby), toky vazeb, souhrn.
- `logic/model-particles.ts` – částice: perioda `clamp(1400 + latence·12, 800, 6000)` ms, max 5 na druh na vazbu,
  barva typu portu, odmítnutí a chybové odpovědi růžově, zpáteční cesta s odpovědí.
- `logic/flow-animator.ts`, `logic/flow-context.ts` – jeden `requestAnimationFrame` na plátno; hodiny `PresentationClock`
  ze `studio-motion` řízené snímkem běhu (Pause zmrazí, Step posune o 280 ms); `MotionEnv` / `browserMotionEnv` ze `studio-motion`.
- `logic/incident-plan.ts` – plánované incidenty v `modelDefinition.incidents` (crash, slow, restore, tick ≥ 1).
- `styles/studio-model-run.css`, blok `studio-model-run`. `prefers-reduced-motion`: bez částic.
