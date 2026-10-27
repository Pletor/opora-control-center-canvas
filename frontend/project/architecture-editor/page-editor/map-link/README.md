# Vazba mapy

Vazba plátna Editoru stránky v jazyce Studia a její pohyb ze skutečného stavu (`docs/zive-zobrazeni-a-knihovna.md` §1–§3).

- `components/ArchitectureLink.tsx` – vlastní hrana React Flow (`map-link`): Bézier `studioBezier` ze Studia, tah podle `edgeLook` (`../logic/canvas-model.ts`, barva a čára podle `carries`), šipka, popisek „pravidlo“, zásahová stopa 18 px; pohyb kreslí `StudioLinkMotion` ze Studia.
- `logic/link-motion.ts` (test vedle) – pravidla Studia (`levelMotion`, `runFailures`) přenesená na vazby plátna: tečky na vazbách `next`, jejichž karta na jednom konci se staví (2 tečky, 1,05 s + 70 ms × pořadí mod 4, strop 40); nově ověřená cesta projede jednou tečkou po vazbách, které realizují její přechody (zdroj na stránce kroku `from`, cíl na stránce kroku `to`; podstránka na plátně je svou stránkou), a konce těch vazeb i podstránky kroků zapulzují 0,9 s; neprošlá cesta má na vazbě `firstFailure` zastavenou červenou tečku s křížkem a důvodem v tooltipu.
- `logic/use-map-motion.ts` – hook pro `PageEditor`: otisky `lastRun`, jednorázový průchod, utichnutí po `passDurationMs`; první načtení nic nepřehraje, při omezeném pohybu se průchod nespouští.
- `styles/map-link.css`, blok `map-link`.

Smyčka pohybu je jedna na plátno: `ArchitectureCanvas` vytvoří `useParticleAnimator()` (Studio, `PresentationClock`, jeden `requestAnimationFrame`, stojí bez teček, při skrytém dokumentu a při `prefers-reduced-motion`) a podá ho vazbám přes `MotionContext`.
