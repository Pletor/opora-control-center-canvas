# sync-badge

Načtení echa a verdiktu Oracle pro otevřený projekt (`logic/use-sync-report.ts`, `GET /api/sync-report`); report čte dashboard procesu. Štítek verdiktu v detailu uzlu a tlačítko „Zacommitovat zadání“ (`/api/opora-commit`) byly odebrány s jednotným detailem karty (`frontend/hub/oporahub-card-drawer`): stav karty má jediný zdroj, snímek agent-state.

Report čte jen dashboard procesu v detailu OporaHubu, a `GET /api/sync-report` trvá na živých projektech 3–6 s. Proto ho `App` načítá s `enabled = hubDetail`: editor a přehled OporaHubu na něj při nečinnosti nesahají. Zavřený detail report podrží; další otevření ho načte znovu jen po změně projektu, prostoru nebo po `refresh()` (`shouldFetchSyncReport`, test `logic/use-sync-report.test.ts`).
