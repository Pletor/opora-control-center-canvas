# Formální podklady

Read-only evidence for TLA+/TLC and Lean in the existing OporaHub overview drawer.
App owns `useFormalVerification`; components receive data and callbacks. GET reads
poll through the shared visibility-aware poller and fence scope, selection and
refresh changes. A selected ID is fetched exactly and never replaced by another.

The parser whitelists public DTO fields, validates scope, limits and explicit
`agent-reported` or `ci-verified` trust (trust and sourceBinding must match; `ci-verified` = base-branch CI workflow, see docs/oporahub-verification.md) with false eligibility/independence flags. Even `passed` has no independent trust or
current correctness eligibility. Configuration and statements render as text;
artifact links use only server-scoped IDs and SHA-256 and download attachments.
Unavailable files have no active link. Revision age remains unknown unless both
accepted-plan sources agree and have loaded successfully.

No human write controls, runner, automatic acceptance or review/merge/card changes.
Pure logic and server-rendered component checks live next to the parser.
