# Review konkrétního návrhu

Parent-owned models combine exact proposal kind/ID readers and the separate
acceptance-policy editor. Native proposal detail components only embed this module
and consult `reviewReady` before enabling their existing acceptance action.

The server classifies risk and enforces policy inside native acceptance transactions.
The UI presents plain-text anchored discussion, reported findings, human resolution,
exact risk acknowledgement, immutable event history and scoped acceptance receipts.
Local human names are not independent votes; missing data is never a passed review.

Scope/ID/revision request generations fence responses and writes. Every explicit
event creates one idempotency key; uncertain writes are not automatically replayed.
Closing a detail discards unsent confirmation. Policy absent/disabled preserves
legacy acceptance once the server context is actually loaded and coherent.

The existing overview drawer owns ✕, Escape, focus containment and focus restoration.
Styles use application theme variables in light/dark and collapse for mobile widths.
See `docs/oporahub-proposal-review.md` for API, limits and bootstrap semantics.
