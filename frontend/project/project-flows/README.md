# Převzatá plátna toku v projektu (`project-flows`)

Plátno toku převzaté z knihovny do projektu (`kind = library_flow`, `owner_ref = opora:project-flow:<nodeId>`, kontrakt `docs/navrhy/2026-11-04-knihovna-platna-toku.md` §1 a §4) je vidět u domény (karta domény na přehledu) i u stránky (karta stránky na mapě domény), jak rozhodl člověk.

- `components/ProjectFlowLinks.tsx` — řádky převzatých pláten uzlu: název otevře plátno (`projectView=library&flow=<id>`), pod ním „vychází z <prvek>@<verze>“ a upozornění na novější verzi v knihovně. Data bere z kontextu.
- `logic/project-flows-context.ts` — kontext, který nastaví `ArchitectureEditor`; karta stránky je rekurzivní, proto ne props.
- `logic/use-project-flows.ts` — seznam workflow projektu, detail kopií a jejich zdrojů; znovu po změně grafu architektury.
- `logic/project-flows.ts` — kopie podle uzlu a řádek odkazu (věty rodokmenu z `library-canvas/logic/lineage.ts`). Test `project-flows.test.ts`.
- `styles/project-flows.css`, předpona `project-flows`.
