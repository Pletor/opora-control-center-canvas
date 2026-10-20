# oporahub-workspace

Prostředí Alt+3 (`environment=hub`) skládá návrhy plánu a existující Oracle dashboard.
Canvas/OporaHub drží plány, GitHub kód; kontrakt je v `docs/oporahub.md`.

`OporaHubWorkspace` dostává `{ view, onRefresh, proposals, changes }` od App a skládá
`PlanChanges`, `ProposalHistory` a `SyncDashboard`. Samo nenačítá ani neukládá data.
`styles/oporahub-workspace.css` používá BEM blok `oporahub-workspace`.
