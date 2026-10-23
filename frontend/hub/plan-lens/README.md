# Lens plánu

Plán jako diagram PR Lens: pro celý projekt (oblasti a předávky mezi nimi) a pro jednu oblast (její karty, vazby z plánu a vazby v kódu z Graphify). Data jsou z `GET /api/oporahub/plan-lens?project&workspace[&area=<id oblasti>]` → `{kind: "plan", area, digest, spec, stats, graphify}`; `spec` je graf PR Lens (schéma 0.7.0), `stats` šest čísel (`areas, cards, withCode, planned, standalone, unassigned`), `graphify` `{available, sourceRevision?}`. Kontrakt: `docs/oporahub-ui.md` („Lens plánu“).

Plátno se nekopíruje: kreslí ho `hub/review-lens/components/LensStage` (líně načtený renderer, obrázek `<img>` z Blob URL, nikdy `innerHTML`, přiblížení, panel části se soubory a vazbami). `LensStage` bere jen `{spec, headSha}` (`LensSource` v `review-lens/logic/lens-read.ts`), panel části ukazuje i odznaky uzlu (`plán`).

- `components/PlanLensButton.tsx` — spouštěč „◫ Lens plánu“ (bez `area`) nebo „◫ Lens oblasti“ (s `area`); drží jen otevřenost okna. Připojený v inspektoru oblasti (`editor/canvas/area/components/AreaPanel.tsx`).
- `components/PlanLensDialog.tsx` — okno zprava přes plátno: ✕ vpravo nahoře, Escape (jen nezastavený, takže průvodce plátna má přednost), klik vedle, návrat fokusu (`useDrawerFocus` z detailu karty).
- `components/PlanLensView.tsx` — skládá čtení (`logic/use-plan-lens.ts`), pruh čísel a plátno. Projektová úroveň ho vkládá jako detail OporaHubu `plan-lens` (tlačítko „◫ Lens plánu“ v hlavičce přehledu, `PLAN_LENS_TARGET`).
- `components/PlanLensStrip.tsx` — čísla plánu, stav Graphify, legenda (plná část = kód existuje, odznak „plán“ = plánováno, šedá vazba „kód“ = vazba z Graphify) a „Obnovit“.
- `logic/plan-lens-read.ts` (test) — URL, přísný parser obálky, `readPlanLens` (odpověď → událost: 200 data + ETag, 304 beze změny, 404 starší server, jinak chyba) a `planLensReducer` (načítání drží data, 304 je potvrdí, chyba data nezahodí, 404 = klidný stav „Lens plánu není na serveru k dispozici“).
- `logic/plan-lens-stats.ts` (test) — skloňovaná čísla, text Graphify a nadpis okna.
- `logic/plan-lens-fixture.ts` — malý platný spec a odpověď pro testy a snímek; test ho ověří schématem a vykreslí.
