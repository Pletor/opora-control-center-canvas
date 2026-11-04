# Akce plátna toku (`library-actions`)

Pohyb plátna mezi knihovnou a projektem (kontrakt `docs/navrhy/2026-11-04-knihovna-platna-toku.md` §1, §3).

- `components/LibraryActions.tsx` — tlačítka podle místa plátna: z knihovny **Převzít do projektu**, z kopie v projektu **Uložit jako vylepšení**, z knihovny agenta **Povýšit do knihovny člověka**. Zápis hlásí callbackem `LibraryCanvas`.
- `components/AdoptForm.tsx` — projekt (výchozí otevřený) a doména nebo stránka, ke které kopie patří (`opora:project-flow:<nodeId>`); bez vazby se kopie pojmenuje podle slugu.
- `components/ContributeForm.tsx` — složka knihovny člověka, titulek a slug nového prvku.
- `logic/adopt-targets.ts` — nabídka domén a stránek z pohledu projektu (`/api/view`); prostor podle druhu projektu (`project-capabilities`). Test `adopt-targets.test.ts`.
- `styles/library-actions.css`, předpona `library-actions`.
