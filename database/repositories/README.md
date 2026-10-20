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
