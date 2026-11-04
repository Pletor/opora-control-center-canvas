# Pohyb bodů (`flow-motion`)

Sdílený základ pohybu po hranách: `ParticleAnimator` (jeden `requestAnimationFrame`, `path.getPointAtLength`, přímý zápis `cx`/`cy`), `PresentationClock` (čas prezentace, skrytý dokument a omezený pohyb čas nepřičítají) a `progress.ts` (poloha tečky v cyklu a jednorázově). Používá ho Studio (`project/studio/studio-motion`) i přehrávání případů (`flow-play`). Testy: `logic/*.test.ts`.
