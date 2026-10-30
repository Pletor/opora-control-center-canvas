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

`intake_entries.py` vkládá a čte vstupy vstupní brány (`intake_entries` i s řádkem FTS5 `intake_entries_fts`, schéma `database/schema/intake_schema.py`); věta je neměnná, měnit se smí jen stanovisko (`set_verdict`: Jev s `only_pending`, srdce). `unclassified` a `jev_calls_on` slouží Jevu a jeho dennímu stropu. Otisk a stanovisko počítá `backend/brain_opora/determinism/intake.py` a `backend/brain_opora/decision/intake.py`, transakci volající. `set_requirement` naváže vstup na požadavek.
`intake_requirements.py` zakládá a čte požadavky brány (`deferred_until` = odložené s podmínkou na milník) a `intake_milestones.py` milníky (kritéria jako JSON; `activate` nahradí aktivní milník oblasti stavem `superseded`, `reject` jen návrh `proposed`). `heart_triggers.py` drží značky spouštěčů „už jsem budil“ (`fire` vrací True jen poprvé) pro milníky i spouštěče karet (`determinism/triggers.py`, který čte i `Executions.reported_at` a `opora_events.last_step_at`). Logika je v `backend/brain_opora/determinism/milestones.py` a `requirements.py` (docs/navrhy/2026-10-30-metriky-a-spoustece.md §4, §5).

`journey_runs.py` čte a zapisuje append-only doklady přehrání cest zákazníka (`journey_runs`, schéma `database/schema/journey_run_schema.py`); validaci a `lastRun` vlastní `backend/project/architecture/journey_runs.py`, transakci volající.
