# oporahub-proofs

Zobrazuje formální důkazy karty (Lean, TLC, shoda s implementací) s úrovní důvěry (`agent-reported`
proti `ci-verified`) a rozhodnutím `verification.fix`, a drawer Kniha důkazů. Data bere z
`GET /api/oporahub/verifications?nodeId=`, `GET /api/oporahub/verifications/ledger` a akcí agent-state
(docs/oporahub-verification.md).
