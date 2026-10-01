Schopnosti projektu podle druhu zdroje (project-capabilities.ts): jediné místo, kde se rozhraní větví podle projektu. Rodič (App) je spočítá a rozdá dílkům v props; žádný dílek si druh projektu nevyhodnocuje sám.

- `projectCapabilities(projectId, activeProject)` — lokální projekt, volné uzly, výchozí pracovní prostor.
- `catalogProfile(settings)` → `ProjectProfile { architecture, tenancy, platform }` — profil projektu z `/api/project-settings` (docs/suplik-a-profil.md). `""` = nenastaveno; starší nastavení bez profilu i neznámé hodnoty se čtou jako nenastaveno. `profileUnset(profile)` říká, že nejsou nastavené architektura ani uživatelé. App profil spočítá a pošle šuplíku Knihovna/Agenti v props.
- `project-profile.ts` — profil slovy: volby s krátkým popisem (`ARCHITECTURE_OPTIONS`, `TENANCY_OPTIONS`) pro kartu profilu i Nastavení → Projekt, `profileWords(profile)` pro hlavičku šuplíku („Web · Modulární monolit · Multitenant“) a malá slova (`architectureWord`, `tenancyWord`) pro důvod „kvůli profilu: …“.

Testy leží vedle: `project-capabilities.test.ts`, `project-profile.test.ts`.
