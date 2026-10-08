# oporahub-workspace

Prostředí OporaHub (třetí prostředí, Alt+3, URL `environment=hub`): plán a dokumentace držené 1:1 s kódem. Pravda je v GitHubu; OporaHub ji jen zrcadlí.

- `components/OporaHubWorkspace.tsx` — dostane `{ view, onRefresh }` od rodiče (`App`): hotový `DashboardView` ze `sync.report` a obnovu reportu. Skládá nadpis, jednu větu o smyslu prostředí a `SyncDashboard` z `frontend/project/sync-dashboard/`.
- `styles/oporahub-workspace.css` — BEM blok `oporahub-workspace`.

Co dílek nedělá: nic nenačítá ani neukládá a nezná projekt ani druh zdroje. Žádné vlastní API; data jsou tatáž, která dřív ukazovala úvodní obrazovka.
