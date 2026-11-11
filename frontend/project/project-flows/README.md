# Převzatá plátna toku v projektu (`project-flows`)

Plátno toku převzaté z knihovny do projektu (`kind = library_flow`, `owner_ref = opora:project-flow:<nodeId>`, kontrakt `docs/navrhy/2026-11-04-knihovna-platna-toku.md` §1 a §4) je vidět u domény (karta domény na přehledu) i u stránky (karta stránky na mapě domény), jak rozhodl člověk.

- `components/ProjectFlowLinks.tsx` — řádky převzatých pláten uzlu: název otevře plátno (`projectView=library&flow=<id>`), pod ním „vychází z <prvek>@<verze>“ a upozornění na novější verzi v knihovně. Data bere z kontextu.
- `components/ProjectFlowsProvider.tsx` — rodič pro editor architektury (`ArchitectureEditor` ho jen obalí): čte plátna (`use-project-flows`), dává kontext a drží okno založení plátna logiky. Plátno toku není graf architektury, proto ho zakládá on, ne editor.
- `components/LogicFlowButton.tsx` — **Nastavit logiku** prvku plátna 2 (verze 4 `docs/navrhy/2026-11-10-platno-2.md`): v Detailu prvku řádka, na štítku `LogicChip` značka ⚙ (plná = plátno existuje). Plátno existuje → otevře `projectView=library&flow=<id>`, jinak okno `LogicFlowDialog`. Jde i na mainu (nezapisuje graf).
- **Dvojklik na prvek** (štítek `LogicChip`, řádek v Detailu boxu) volá `onOpenLogic` z kontextu: plátno existuje → otevře ho, jinak ho `ProjectFlowsProvider` rovnou založí prázdné (`createElementFlow`, titulek `logicFlowTitle`) a otevře, bez okna; druhý dvojklik během zakládání nic nepošle. Selže-li založení, ukáže se okno `LogicFlowDialog` s důvodem.
- `components/LogicFlowDialog.tsx` — okno **Prázdné plátno** (`POST /api/library/project-flows`, `createElementFlow`) / **Z knihovny…** (plátna s aktivní verzí → `adopt` s `nodeId`); hotové plátno se rovnou otevře.
- `logic/project-flows-context.ts` — kontext (`flows`, `onOpen`, `onSetLogic`, `onOpenLogic`), který nastaví `ProjectFlowsProvider`; karta stránky je rekurzivní a štítek prvku leží hluboko, proto ne props.
- `logic/use-project-flows.ts` — seznam workflow projektu, detail kopií a jejich zdrojů; znovu po změně grafu architektury.
- `logic/project-flows.ts` — kopie podle uzlu, uzel z `owner_ref` (`flowNodeOf`), výběr z knihovny (`libraryChoices`) a řádek odkazu (věty rodokmenu z `library-canvas/logic/lineage.ts`). Test `project-flows.test.ts`.
- `styles/project-flows.css`, bloky `project-flows` a `project-flows-dialog`.
