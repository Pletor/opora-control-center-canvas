# oporahub-workspace

Prostředí Alt+3 (`environment=hub`) skládá návrhy plánu a existující Oracle dashboard.
Canvas/OporaHub drží plány, GitHub kód; kontrakt je v `docs/oporahub.md`.

`OporaHubWorkspace` dostává `{ view, onRefresh, proposals, changes, evidence }` od App a skládá
`PlanChanges`, `GitEvidence`, `ProposalHistory` a `SyncDashboard`. Samo nenačítá ani neukládá data.
GitHub důkazy jsou samostatná historická pozorování pro přijatou revizi a přesné SHA; jejich hook v App obnoví kontext po přijetí zadání.
`styles/oporahub-workspace.css` používá BEM blok `oporahub-workspace`.
