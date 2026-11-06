# agi-pletor/dashboard

Velín AGI Pletor: stránka `?screen=pletor` s levou navigací po částech (kontrakt `docs/navrhy/2026-11-05-pletor-opora-dashboard.md`).

- `components/PletorDashboard.tsx`: rodič; drží aktivní část (`part=` v adrese), Esc a titulek s focusem. Skládá dílky `Dashboard*` jednotlivých částí a vkládá `PletorWorkshop`.
- `logic/dashboard-route.ts`: části, parsování a zápis `part=`; `overview-cards.ts`: stav Pletora na karty Přehledu; `use-voice-list.ts`: hlasy serveru; `*-view.ts`: odpovědi API na bezpečné pohledy částí.
- `styles/pletor-dashboard.css`: blok `pletor-dashboard`; `pletor-dashboard-parts.css`: tabulky a prvky částí.

Všechny části jsou funkční: Přehled, Mozek a LLM, Hlas, Dílna (V1), Srdce a Podklady (V2), Monitoring a Rozhovor (V3), Nastavení (V4).

Linie (`DashboardLinie`, kontrakt `docs/navrhy/2026-11-06-linie-editor-a-vynuceni.md` §6) je editor řádků a kuliček z `GET /api/pletor/linie/board` (`LinieBoard`, `LinieBall`, `LinieLegend`, formuláře `LinieRowForm` / `LinieWorkForm`, detail `LinieDetail` s akcemi jen pro člověka, logika `linie-board.ts` a `linie-work.ts`, styly `pletor-dashboard-linie-editor.css` a `pletor-dashboard-linie-detail.css`); přepínač „Git graf“ ukáže graf větví z M1 (`LinieGraph`, `linie-graph.ts`, `linie-view.ts`) a řádka stavu main pod lištou drží server, nasazení a stav ochrany.

L6 (`docs/navrhy/2026-11-06-linie-barvy-a-zamereni.md`): barvu větve dává `linie-color.ts` (`branchColor`: každý kořen feat vlastní odstín z hashe jména, děti ho dědí a s hloubkou blednou), spojnice tečou gradientem a puntík v kuličce ukazuje cíl. Sbalení podstromu a zaměření `?branch=` řeší `linie-fold.ts` (ruční řádek sbalení ukládá na server, ostatní v `localStorage` `pletor.linie.folded`); editor má celou šířku a detail, Cesta nebo commit se otevře vpravo jako panel.

Dluh V1: část Hlas je jen ke čtení. Výběr hlasu a „Vyzkoušet“ jsou v `usePletorVoice`, který drží jen `PletorWindow`; výběr zůstává v kokpitu (ozubené kolo). Vyřešit vytažením hlasu do sdíleného kontextu.
