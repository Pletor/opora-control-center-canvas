Paměť agenta podle role: co daná kompetence (frontend, backend, databáze…) ví napříč projekty a co ví u jedné karty.

- `roles.py` — registr rolí z `library/agent-roles.json`; id role je zároveň `user` v OpenVikingu.
- `memory_service.py` — jediné místo, kde Opora sahá na paměť: `status`, `provision_roles`, `recall`, `remember`, `lend`, `mirror_workspace`, `commit_card`, plus `AppSettings` (přepínač a klíče rolí pro celou aplikaci v `registry.sqlite`).

Přenos drží `backend/integrations/openviking_client.py`. Aplikace tudy **nespouští žádný model**: zapisuje texty a otevírá session, extrakci dělá OpenViking uvnitř sebe.

**Identitu určuje klíč.** Server běží v režimu `api_key`, takže role není hlavička, ale vlastní uživatel OpenVikingu s vlastním klíčem. Správcovský klíč (`OPORA_OPENVIKING_ADMIN_API_KEY`) umí jediné — rozdat rolím klíče (`provision_roles`); data čte a zapisuje vždy klíč té role. Klíče leží v `app_settings` pod `openviking.roleKeys` a **nikdy** neodcházejí v odpovědi ani do logu.

Když je paměť vypnutá, server dole nebo role bez klíče, každá metoda to pravdivě řekne (`disabled` / `unavailable` / `needs_provisioning`) a Opora funguje dál. Kontrakt a provoz: `docs/pamet-agentu.md`.
