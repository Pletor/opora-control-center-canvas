Načítání a verze předloh, checklisty, zpětná vazba.

`harness_kit.py` validates the optional `spec.fields.harness` payload and reads it
from an already authenticated immutable assignment. The specification and execution
owners provide storage, acceptance, source coverage and replay; this module opens
no files, starts no tools and adds no event store. See [the contract](../../docs/harness-kit.md).

`harness_learning.py` derives selected-kit outcomes from native outbox callbacks
inside their source transaction. `harness_learning_rates.py` reads scoped rates;
the schema/repository live under `database/`. This is a durable projection of the
existing outbox, not another event bus. It never trusts a worker's verified label.
