# card-face

Tvář karty na plátně Editoru: druh, kdo kartu drží, název, jeden stavový řádek (zdraví · etapa · důvod),
postup kroků a nejvýš jedna patička (brána / blokace / rozhodnutí). Data bere výhradně z `cards[]` a
`decisions[]` agent-state (`logic/card-face.ts`, test `card-face.test.ts`); pod 45 % zoomu kreslí glyf (kruh postupu + název). Růst karty pro plátno 3 (`logic/face-growth.ts`, test vedle): tvar rámečku seed/bud/leaf/prop (`node-card--grow-*`), kruh postupu z kroků, tečky Z/K/S/B (K z `cards[].mirror`: ok zelená, part modrá, bad plná červená, `null` čárkovaně; B z `cards[].future`: clean zelená, warning modrá, blocked červená, `null` čárkovaně) a živý pulz při lease nebo běžící exekuci; dílky `components/FaceGrowth.tsx`.
Klik na rozhodnutí otevře detail karty přes `frontend/hub/oporahub-card-drawer/open.ts`.
Pod stavovým řádkem stojí odznak PR v barvách GitHubu (`face.pr` z `cards[].pr`, dílek `frontend/shared/pr-badge`); uzavřená karta ho nemá.

Pohyb jen ze skutečného stavu: karta ve stavu `decision` („čeká na tebe“, `logic/card-face.ts`) má čárkovaný zlatý prstenec `::after` s animací `node-card-await` (1,85 s); tečka živého dělníka pulzuje (1,1 s). Při `prefers-reduced-motion` bez animace, prstenec svítí napevno.

Stopa karty (docs/navrhy/2026-10-31-viditelnost-srdce-a-karet.md, B; logika `logic/face-change.ts`, test `face-change.test.ts`):

- **Pořadí:** karta s `cards[].order` má v hlavičce odznak `F·PP` (`302` → `3·02`, `1205` → `12·05`), titulek „Pořadí podle záměru“ (`face.order`, `data-oh-order`).
- **Poslední změna:** pod stavovým řádkem dílek `components/FaceLastChange.tsx` ukáže „kdo · kdy · co“ (`face.change`): kdo = „Srdce“ (agent `heart`), „Vy“ (actor `human`), jinak „Dělník <jméno>“; kdy = dnes HH:MM, „včera“, letos „6. 10.“, jinak datum; co = `label`, jinak `actionLabel(path)` ze záznamu činnosti. Data: `logic/use-latest-by-node.ts`, jeden dotaz `GET /api/activity-log/latest-by-node` pro celé plátno v `Board`, obnovený s novým snímkem agent-state nebo změnou plátna; do tváře jde přes `layer-nodes.ts` (`latest`). Klik ohlásí `onHistory` → akce karty `history` → App otevře záznam činnosti s filtrem „Jen vybraná karta“ (`ActivityLogTools`, prop `request`) a kartu vybere.
- **Čerstvost:** změna mladší než 10 minut (`isFresh`) karta jednou krátce blikne obrysem (`card-face__flash`); při `prefers-reduced-motion` nic. Glyf pod 45 % zoomu nic z toho neukazuje.
- **Stopa práce:** celý postup kroků je tlačítko (`data-oh-open-trail`) s tichým „stopa ›“ vpravo. Klik ohlásí `onTrail` → akce karty `trail` → App otevře boční menu se stopou práce karty (`editor/block-panel`, režim karty bez bloku).
