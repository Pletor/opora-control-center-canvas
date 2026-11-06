# agi-pletor/dashboard

Velín AGI Pletor: stránka `?screen=pletor` s levou navigací po částech (kontrakt `docs/navrhy/2026-11-05-pletor-opora-dashboard.md`).

- `components/PletorDashboard.tsx`: rodič; drží aktivní část (`part=` v adrese), Esc a titulek s focusem. Skládá dílky `Dashboard*` jednotlivých částí a vkládá `PletorWorkshop`.
- `logic/dashboard-route.ts`: části, parsování a zápis `part=`; `overview-cards.ts`: stav Pletora na karty Přehledu; `use-voice-list.ts`: hlasy serveru; `*-view.ts`: odpovědi API na bezpečné pohledy částí.
- `styles/pletor-dashboard.css`: blok `pletor-dashboard`; `pletor-dashboard-parts.css`: tabulky a prvky částí.

Všechny části jsou funkční: Přehled, Mozek a LLM, Hlas, Dílna (V1), Srdce a Podklady (V2), Monitoring a Rozhovor (V3), Nastavení (V4).

Linie (`DashboardLinie`, kontrakt `docs/navrhy/2026-11-06-linie-editor-a-vynuceni.md` §6) je editor řádků a kuliček z `GET /api/pletor/linie/board` (`LinieBoard`, `LinieBall`, `LinieLegend`, formuláře `LinieRowForm` / `LinieWorkForm`, detail `LinieDetail` s akcemi jen pro člověka, logika `linie-board.ts` a `linie-work.ts`, styly `pletor-dashboard-linie-editor.css` a `pletor-dashboard-linie-detail.css`); přepínač „Git graf“ ukáže graf větví z M1 (`LinieGraph`, `linie-graph.ts`, `linie-view.ts`) a karta MAIN drží server, nasazení a stav ochrany.

Dluh V1: část Hlas je jen ke čtení. Výběr hlasu a „Vyzkoušet“ jsou v `usePletorVoice`, který drží jen `PletorWindow`; výběr zůstává v kokpitu (ozubené kolo). Vyřešit vytažením hlasu do sdíleného kontextu.
