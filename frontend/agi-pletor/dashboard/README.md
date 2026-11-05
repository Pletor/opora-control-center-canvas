# agi-pletor/dashboard

Velín AGI Pletor: stránka `?screen=pletor` s levou navigací po částech (kontrakt `docs/navrhy/2026-11-05-pletor-opora-dashboard.md`).

- `components/PletorDashboard.tsx`: rodič; drží aktivní část (`part=` v adrese), Esc a titulek s focusem. Skládá dílky `DashboardOverview`, `DashboardBrain`, `DashboardVoice` a vkládá `PletorWorkshop`.
- `logic/dashboard-route.ts`: části, parsování a zápis `part=`; `overview-cards.ts`: stav Pletora na karty Přehledu; `use-voice-list.ts`: hlasy serveru.
- `styles/pletor-dashboard.css`: blok `pletor-dashboard`.

Milník V1: Přehled, Mozek a LLM, Hlas, Dílna. Srdce a Podklady (V2), Monitoring a Rozhovor (V3), Nastavení (V4) jsou zatím jen místo s hláškou.

Dluh V1: část Hlas je jen ke čtení. Výběr hlasu a „Vyzkoušet“ jsou v `usePletorVoice`, který drží jen `PletorWindow`; výběr zůstává v kokpitu (ozubené kolo). Vyřešit vytažením hlasu do sdíleného kontextu.
