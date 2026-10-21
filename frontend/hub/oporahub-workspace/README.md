# oporahub-workspace

Prostředí Alt+3 (`environment=hub`) skládá návrhy plánu a existující Oracle dashboard.
Canvas/OporaHub drží plány, GitHub kód; kontrakt je v `docs/oporahub.md`.

`OporaHubWorkspace` dostává `{ view, onRefresh, proposals, changes, graphProposals, evidence, executions, reviewPolicy, reconciliation }` od App a skládá
`GraphProposals`, `PlanChanges`, `ExecutionReceipts`, `GitEvidence`, `ReviewPolicy`, `GithubReconciliation`, `ProposalHistory` a `SyncDashboard`. Samo nenačítá ani neukládá data.
GitHub důkazy jsou samostatná historická pozorování pro přijatou revizi a přesné SHA; jejich hook v App obnoví kontext po přijetí zadání.
Pravidla review mají vlastní aktuální vyhodnocení a expiraci. Trvalé sledování PR má oddělený stav serverového procesu, pozorovaný stav PR a historickou vazbu k původní revizi; sloučení nepotvrzuje review ani dokončení karty.
`styles/oporahub-workspace.css` používá BEM blok `oporahub-workspace`.
