Panel Asistent: kanál člověka do srdce OPORY (kontrakt `docs/brain-heart-channel.md`). Obsah je `frontend/layout/heart-channel/` (`HeartChannel`); dosavadní asistent s úkoly a konverzací byl smazán v H2b2b.

Tři velikosti: `minimized` (lišta vpravo dole nad minimapou), `side` (panel vpravo, cca 480 px) a `full` (celá plocha pod horní lištou). Velikost se ukládá jednou pro aplikaci (`localStorage` `opora:assistant:v1`), nikdy per projekt.

Dílky (`components/`):

- `AssistantButton`: tlačítko v pravém rohu horní lišty, otevře a zavře panel.
- `AssistantPanel`: rodič. Drží velikost, stav brány projektu (`logic/use-gate.ts`) a zkratku `Esc` (zmenší o stupeň); skládá hlavičku a `HeartChannel`, který dostane jen projekt, prostor a stav brány.
- `PanelHead`, `SizeSwitch`: hlavička se jménem kanálu a tři ikony velikosti.
- `MinimizedBar`: minimalizovaná lišta.
- `PanelNotice`: chybí projekt.

Logika (`logic/`):

- `assistant-prefs.ts` (test vedle): velikost panelu a přechody velikostí; starší záznamy s modelem, rozsahem nebo kanálem se čtou, ta pole se ignorují.
- `use-gate.ts`: stav brány projektu (`GET /api/brain/gate-setting`) a její zapnutí (`POST /api/brain/gate-setting`).
- `use-panel-keys.ts`: `Esc` zmenší panel, jen když je fokus v panelu.

Akce jinde v aplikaci (Kancelář „Posadit agenta“, živý panel domény „Zadat srdci“) posílají připravený text srdci (`POST /api/brain/heart/messages`) přes jediný callback v `App` a panel otevřou.

Styl: `styles/assistant-panel.css` (bloky `assistant-button`, `assistant-panel`).
