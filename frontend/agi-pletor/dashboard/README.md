# agi-pletor/dashboard

Velín AGI Pletor: stránka `?screen=pletor` s levou navigací po částech (kontrakt `docs/navrhy/2026-11-05-pletor-opora-dashboard.md`).

- `components/PletorDashboard.tsx`: rodič; drží aktivní část (`part=` v adrese), Esc a titulek s focusem. Skládá dílky `Dashboard*` jednotlivých částí a vkládá `PletorWorkshop`.
- `logic/dashboard-route.ts`: části, parsování a zápis `part=`; `overview-cards.ts`: stav Pletora na karty Přehledu; `use-voice-list.ts`: hlasy serveru; `*-view.ts`: odpovědi API na bezpečné pohledy částí.
- `styles/pletor-dashboard.css`: blok `pletor-dashboard`; `pletor-dashboard-parts.css`: tabulky a prvky částí.

Všechny části jsou funkční: Přehled, Mozek a LLM, Hlas, Dílna (V1), Srdce a Podklady (V2), Monitoring a Rozhovor (V3), Nastavení (V4).

Linie (`DashboardLinie`, `LinieBranchDetail`, `logic/linie-view.ts`, kontrakt `docs/navrhy/2026-11-06-velin-git-linie.md` §5) ukazuje main, develop, server s nasazením a větve s přijetím a náhledem; člověk odtud spouští náhledy, přijímá hlavu větve do rodiče a zapisuje nasazené sha.

Dluh V1: část Hlas je jen ke čtení. Výběr hlasu a „Vyzkoušet“ jsou v `usePletorVoice`, který drží jen `PletorWindow`; výběr zůstává v kokpitu (ozubené kolo). Vyřešit vytažením hlasu do sdíleného kontextu.
