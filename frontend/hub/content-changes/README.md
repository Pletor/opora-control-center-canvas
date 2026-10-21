# Změny obsahu

Typed list/detail readers and scoped request generations retain exact proposal IDs.
`useContentChanges` owns periodic reads, identity negotiation, adoption acknowledgement
and serialized accept/rebase writes. It never retries uncertain mutations automatically.
Scope, selection and refresh fence late responses; closing clears confirmation.

The overview and its existing accessible drawer compose this module. The three-column
diff renders accepted, observed working and proposed values as text; full JSON is
downloadable. First adoption explicitly reviews the complete captured baseline.
Human acceptance uses the exact ID and accepted head through the content API.

No runtime demonstration data. Missing models/API show unavailable information.
Creation is agent-facing through the JSON recipe. Images/external references remain
references and are not treated as verified bytes. See `docs/oporahub-content-changes.md`.
