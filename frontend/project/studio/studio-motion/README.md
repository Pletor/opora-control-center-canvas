# Pohyb Skutečnosti

Etapa S3 kontraktu `docs/studio.md` (§2 pohyb Skutečnosti), hodnoty z `docs/zive-zobrazeni-a-knihovna.md` §3. Ve Skutečnosti se hýbe jen to, co se opravdu děje; simulace ani ovládání RUN tu nejsou (to je vrstva MODEL).

- **Staví se:** vazba aktuální úrovně, jejíž zdroj nebo cíl je ve stavu „staví se“, nese 2 tečky 5 px se září `0 0 6px` barvy `carries`, cyklus 1,05 s + 70 ms × (pořadí mod 4), lineárně; nejvýš 40 vazeb.
- **Nově ověřená cesta:** když `lastRun` cesty přibude nebo se změní (`at`) a je prošlý a ne zastaralý, projede po vazbách trasy na této úrovni jednou tečka (přechod za přechodem, 1,05 s každý) a karty kroků jednou zapulzují (0,9 s). První načtení nic nepřehraje.
- **Cesta právě běží** (`running`, `docs/brana-cesty.md` §3a): po vazbě aktuálního přechodu obíhají 2 tečky v barvě ověření v cyklu 1,05 s, dokud server běh hlásí; při omezeném pohybu štítek „cesta běží“. Čtení cest se během běhu zrychlí na 3 s (`runsPollMs`).
- **Selhání:** neprošlá cesta má na vazbě přechodu `firstFailure` zastavenou červenou tečku `#ff5c78` (`--studio-failure`) s křížkem v půli trasy a důvodem v tooltipu.
- **Omezený pohyb** (`prefers-reduced-motion: reduce`): žádné tečky ani pulz, na stavěné vazbě štítek „staví se“; selhání zůstává (je statické). Skrytý dokument smyčku zastaví a čas se po návratu nedohání.

Soubory:
- `components/StudioLinkMotion.tsx` – pohyb jedné vazby, vykreslený uvnitř `StudioLink`; tečky přihlásí animátoru plátna.
- (přesunuto do `shared/flow-editor/flow-motion/logic/`) `presentation-clock.ts` – `PresentationClock` z prototypu `04.Architektura-projektu/prototype/animations.mjs` (test převedený z `test/presentation-clock.test.mjs`).
- (přesunuto do `shared/flow-editor/flow-motion/logic/`) `particle-animator.ts` – jeden `requestAnimationFrame` pro celé plátno, `path.getPointAtLength`, přímý zápis `cx`/`cy`; prostředí vstříknuté kvůli testu.
- `logic/motion-plan.ts` – výběr stavěných vazeb, časování, pohyb vazeb úrovně (`levelMotion`).
- `logic/journey-route.ts` – přechod `from → to` mezi kroky → stránky kroků → karty a vazba aktuální úrovně.
- `logic/run-events.ts` – nový prošlý doklad oproti minulému čtení, první selhání s větou do tooltipu, právě přehrávaný přechod (`runningHops`).
- `logic/use-studio-motion.ts` – hook pro rodiče (`Studio.tsx`): pohyb vazeb a karty k pulzu; průchod po svém trvání sám utichne.
- `logic/motion-context.ts` – animátor plátna v kontextu pro vazby uvnitř React Flow.
- `styles/studio-motion.css`, blok `studio-motion` (tečky, štítek, selhání, `@keyframes studio-motion-pulse` na uzlu React Flow).

Testy: `logic/*.test.ts` (`npm test`).
