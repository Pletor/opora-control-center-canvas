# Plátno toku v knihovně (`library-canvas`)

Obrazovka jednoho plátna toku (kontrakt `docs/navrhy/2026-11-04-knihovna-platna-toku.md` §0 K2, §1, §2, §4). Otevírá se z panelu Komponenty nebo z odkazu u domény a stránky, v adrese `projectView=library&flow=<workflowId>` (vyřizuje App, `project/shell/logic/project-view.ts`).

- `components/LibraryCanvas.tsx` — rodič: drží data, zobrazenou verzi, neuloženou úpravu a zápis. Skládá hlavičku (titulek, místo prvku, rodokmen „vychází z <prvek>@<verze>“ s odkazem, upozornění na novější verzi v knihovně, počet odvozených), `library-versions/`, `library-actions/` a sdílený `shared/flow-editor/FlowEditor` v režimu plátna toku (`frames`: poznámky, rámce, inspektor polí uzlu; `nodePorts`; `checkErrors`).
- `logic/library-api.ts` — URL a volání `/api/library/*` a engine toků (verze, aktivace draft → candidate → active, návrat, `node-ports`, `graph-check`), slug z titulku, místo prvku z `owner_ref`. Test `library-api.test.ts`.
- `logic/node-ports.ts` — na co se ptát `POST /api/flow/node-ports`: porty uzlů dynamických typů a uzlů s chybovým výstupem, varianty typů z výčtových parametrů registru (paleta podle portu nabídne vektorové úložiště jako nástroj). Test `node-ports.test.ts`.
- `logic/use-library-flow.ts` — katalog s variantami (jednou za načtení stránky), detail plátna a detail zdroje rodokmenu. `logic/use-flow-checks.ts` — porty uzlů a kontrola grafu chvíli po úpravě.
- `logic/lineage.ts` — věty rodokmenu (použije je i `project/project-flows`). Test `lineage.test.ts`.
- `styles/library-canvas.css`, předpona `library-canvas`.

Plátno se nespouští: místo „Připraveno ke spuštění“ editor ukáže pás kontroly grafu. Zápis do části Člověk smí jen člověk v UI, do části Agent i agent (pravidla hlídá backend).
