# Linie stavby: jak PR vznikají, slučují se a uklízí

Platí pro OPORU i agent-office od 2026-11-03, kdy se staví nový základ (`docs/navrhy/2026-11-03-novy-zaklad.md`). Staré pravidlo „malé PR jen z čerstvého main, žádné řetězy, slučuje člověk“ je zrušené. Brzdilo stavbu, která jde po patrech.

## 1. Vlak PR podle kontraktu

- Velká stavba jde jako **vlak**: pořadí PR je dané kontraktem (např. PR 1 engine → PR 2 srdce v1 → …). Další PR se větví z větve předchozího a jeho `base` je ta větev. Nečeká se na sloučení.
- **Vlak má jednoho vlastníka**, hlavní vlákno, které ho naplánovalo. Drží pořadí, rebase vagonů a slučování.
- Vagon dělá jednu věc z kontraktu. Velikost určuje kontrakt, ne limit řádků. Nejmenší úplná změna podle ponytailu.
- Mimo vlak, u drobných oprav, platí: větev z čerstvého `origin/main`, jeden PR.

## 2. Záměr před kódem

- Práce začíná kontraktem nebo kartou a ohlášením záměru (soubory, data, API). Před stavbou najdi, co už existuje (`main`, otevřené PR, `docs/`).
- Když je stávající základ slabý, **zbourej ho a postav znovu**. Nestav na něm a nezachovávej ho kvůli kompatibilitě. Mazání bere s sebou testy, styly a README.

## 3. Slučování

- Slučuje **agent sám** po ověření: cílené `uv run pytest`, `npm test`, `npm run build` zelené a výstup v PR nebo odpovědi.
- Vlak se slučuje **zdola nahoru** (squash). Po sloučení vagonu přepne vlastník `base` dalšího PR na `main` a udělá rebase (`git rebase --onto origin/main <stará-base>`), pak force-push s lease na vlastní větev.
- Člověk slučování nebrzdí. Může kdykoli zastavit vlak nebo vrátit směr.

## 4. Nasazení po sloučení

- Po sloučení: `ff pull` hlavního checkoutu, build klienta i serveru, restart, ověření, že server i klient běží z `main` HEAD.
- Server 8740 běží z pracovního stromu: restart až po sloučení, ne během práce subagenta. Zabít celý strom procesů a ověřit novou routu.

## 5. Úklid

- Kdo založil větev nebo worktree, ten je po sloučení smaže. Cizí se nemaže.
- GitHub maže hlavu větve po sloučení automaticky.

## 6. PR Lens

Diagram PR Lens (lokální skill `pr-lens`, bez API) je vstup pro review, ne brána. Spec se posílá do OPORY (`POST /api/oporahub/review-jobs/lens`) a karta ho kreslí v záložce Lens.
