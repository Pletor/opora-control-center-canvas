Schránka zadání v UI (záložka Schránka u sektoru a karty s vlastní schránkou, sekce „Schránka zadání“ v inspektoru plátna/vrstvy bez výběru): doslovné verzované zadání ze serveru `GET /api/brief-vault` a `GET /api/brief-vault/fragment` (návrh `docs/navrh-schranka-zadani.md`, část UI). Jen čtení; zápis (research, MVP, vložení jako karty) sem zatím nepatří.

- `logic/brief-vault-model.ts` — tvary odpovědí, pruh pokrytí (`coverageOf`: listy druhu brief, každý v jednom segmentu MVP vloženo · vloženo · v researchu · uloženo · změněno), kulička stavu (`statusDot`), čipy karty a „změněno po vložení“ (`briefChips`, `changedSinceInsert` z `nodes[].fragmentRefs`).
- `logic/use-brief-vault.ts` — načtení stromu (obnova se stavem plátna a každých 15 s) a detailu fragmentu s výběrem revize.
- `components/BriefVaultPanel.tsx` (pruh + strom), `FragmentDetailView.tsx` (text, historie, karty, Podněty), `BriefChips.tsx` (čipy „Ze schránky“ v záložce Zadání), `BriefVaultScope.tsx` (schránka plátna nebo vrstvy).
- Odznak ⚠ „zadání se změnilo“ kreslí `canvas/node-card/components/CardHead.tsx` z `CardView.briefChanged`, který doplní Board.
