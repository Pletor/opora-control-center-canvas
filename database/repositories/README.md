# Repozitáře dat

Přístup k datům vyčleněný z modulů, které tabulky vlastní (viz `database/README.md`).

`opora_changesets.py` vlastní autoritativní SQLite záznamy změn zadání:
`opora_spec_proposals` (neměnné návrhy), `opora_spec_revisions` (neměnné přijaté
revize) a `opora_spec_refs` (aktuální přijatá hlava projektu/prostoru).
Při čtení kontroluje obsahový otisk a rozsah záznamu. Zápis vyžaduje transakci
volajícího; přijetí návrhu tak může atomicky změnit dokumenty i ukazatel hlavy.
Není to obnovitelný index legacy souborové historie `opora_commits`.

Doménové operace a oprávnění jsou v `backend/canvas/opora_changesets.py`
a `opora_acceptance.py`. Kontrakt: `docs/oporahub.md`.

`opora_executions.py` ukládá autoritu vykonávání: trvalé `opora_execution_epochs`, záznamy `opora_executions` s neměnným zadáním a soukromým tokenem, a idempotentní `opora_execution_results`. Transakci vlastní doménová služba a rezervace se sdílí s původní tabulkou `card_leases`. Token se neposílá do veřejného výpisu. Aditivní schéma je v `database/schema/opora_execution_schema.py`.

`journey_runs.py` čte a zapisuje append-only doklady přehrání cest zákazníka (`journey_runs`, schéma `database/schema/journey_run_schema.py`); validaci a `lastRun` vlastní `backend/project/architecture/journey_runs.py`, transakci volající.
