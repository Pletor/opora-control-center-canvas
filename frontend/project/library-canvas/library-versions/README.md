# Lišta verzí plátna toku (`library-versions`)

Verze plátna toku v knihovně (kontrakt `docs/navrhy/2026-11-04-knihovna-platna-toku.md` §1: draft → active s historií a návratem, bez schválení). Vzor je lišta záměru stránky (`project/intent-canvas/intent-versions/`), jen bez kandidáta a schvalování.

- `components/LibraryVersionBar.tsx` — výběr verze z historie, štítek stavu, „Uložit draft“ a „Zahodit“ u neuložené úpravy a jedna akce podle stavu: Aktivovat (draft), Vrátit na tuto verzi (historie), Návrat na předchozí (aktivní). Data a zápis drží `LibraryCanvas`.
- `components/ProposalBar.tsx` — čekající návrh srdce u plátna člověka (K3, kontrakt §5): „Srdce navrhuje změnu: <poznámka>“, souhrn rozdílu proti aktivní verzi (`shared/flow-editor/logic/graph-diff`, plátno ukáže značky uzlů), Přijmout (aktivovat draft) a Zamítnout (draft do historie s důvodem).
- `logic/library-versions.ts` — zobrazená verze, akce podle stavu, čekající návrh srdce (`pendingProposal`) a pořadí historie; test `library-versions.test.ts`.
- `styles/library-versions.css`, předpona `library-versions`.
