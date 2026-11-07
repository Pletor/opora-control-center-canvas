# agi-pletor/dashboard

Velín AGI Pletor: stránka `?screen=pletor` s levou navigací po částech (kontrakt `docs/navrhy/2026-11-05-pletor-opora-dashboard.md`).

- `components/PletorDashboard.tsx`: rodič; drží aktivní část (`part=` v adrese), Esc a titulek s focusem. Skládá dílky `Dashboard*` jednotlivých částí a vkládá `PletorWorkshop`.
- `logic/dashboard-route.ts`: části, parsování a zápis `part=`; `overview-cards.ts`: stav Pletora na karty Přehledu; `use-voice-list.ts`: hlasy serveru; `*-view.ts`: odpovědi API na bezpečné pohledy částí.
- `styles/pletor-dashboard.css`: blok `pletor-dashboard`; `pletor-dashboard-parts.css`: tabulky a prvky částí.

Všechny části jsou funkční: Přehled, Mozek a LLM, Hlas, Dílna (V1), Srdce a Podklady (V2), Monitoring a Rozhovor (V3), Nastavení (V4).

Linie (`DashboardLinie`, kontrakt `docs/navrhy/2026-11-06-linie-editor-a-vynuceni.md` §6) je editor řádků a kuliček z `GET /api/pletor/linie/board` (`LinieBoard`, `LinieBall`, `LinieLegend`, formuláře `LinieRowForm` / `LinieWorkForm`, detail `LinieDetail` s akcemi jen pro člověka, logika `linie-board.ts` a `linie-work.ts`, styly `pletor-dashboard-linie-editor.css` a `pletor-dashboard-linie-detail.css`); přepínač „Git graf“ ukáže graf větví z M1 (`LinieGraph`, `linie-graph.ts`, `linie-view.ts`) a řádka stavu main pod lištou drží server, nasazení a stav ochrany.

L6 (`docs/navrhy/2026-11-06-linie-barvy-a-zamereni.md`): barvu větve dává `linie-color.ts` (`branchColor`: každý kořen feat vlastní odstín z hashe jména, děti ho dědí a s hloubkou blednou), spojnice tečou gradientem a puntík v kuličce ukazuje cíl. Sbalení podstromu a zaměření `?branch=` řeší `linie-fold.ts` (ruční řádek sbalení ukládá na server, ostatní v `localStorage` `pletor.linie.folded`); editor má celou šířku a detail, Cesta nebo commit se otevře vpravo jako panel.

L7 UI (`docs/navrhy/2026-11-06-linie-rebrand.md` §6): nahoře fronty odpovědnosti (`LinieQueues`, `linie-queues.ts`: zařazení podle `summary.key`, počty s jednotkou, fronty bez zdroje „— (zatím bez zdroje)“), lišta `LinieToolbar` (měřítko, Vrstvy v `localStorage` `pletor.linie.layers`), editor jako jediný posuvný prvek (`LinieBoard` skládá sticky `LinieNames` a `LiniePlot` + `LinieLink`; šířka názvů `pletor.linie.names`, `linie-prefs.ts`). Čas je společná souřadnice (`linie-zoom.ts` + hook `use-linie-zoom.ts`: kolečko kolem kurzoru, Shift+kolečko posun, tažení ruka, `Vše` / `Teď` / `↻ Výchozí`); kulička se nikdy neposouvá, kolize řeší popisky (`linie-labels.ts`: vybraná přednost, dvě patra, shluk „+N“). Vpravo `LiniePletor` (výrok jen z os a souhrnu, stáří zdrojů, akce `allowed`/`blocked`, `linie-summary.ts`) a detail se záložkami Souhrn / Git (`LinieDetailSummary`, `LinieDetailGit`). Stálou polohu výběru a pořadí Esc drží `linie-keep.ts`. Styl panelů `pletor-dashboard-linie-panel.css`.

Dluh V1: část Hlas je jen ke čtení. Výběr hlasu a „Vyzkoušet“ jsou v `usePletorVoice`, který drží jen `PletorWindow`; výběr zůstává v kokpitu (ozubené kolo). Vyřešit vytažením hlasu do sdíleného kontextu.
