# Přehled domén (Mapy architektury)

První obrazovka editoru architektury: řádek Produkce a řádek Vývoj, v každém karty domén s ikonou druhu (web / aplikace / administrace), hostem, „druh · účel“, ID a odkazem **Otevřít mapu projektu**. Zachovává formulář domény a oddělení hostu ze starší sdílené struktury.

- `components/ArchitectureLanding.tsx` skládá dílky a drží rozepsaný formulář a potvrzení oddělení; ukládání jde callbackem do `ArchitectureEditor`.
- `components/DomainCard.tsx`, `DomainKindIcon.tsx`, `SplitConfirm.tsx` dostávají hotová data v props. `DomainCard` s `live` ukáže žeton webu a `DomainWork` (věta s počty, rozbalí stěsnaný strom worktree z `live-status/`).
- Hlavička ukazuje souhrn hlavních relací a „Nová hlavní relace“; worktree bez domény jsou ve skupině **Nepřiřazené**. Živá data dodá `ArchitectureEditor` (`LandingLive`).
- `logic/domain-kind.ts` odvozuje druh z hostu (`app.` / `admin*` / jinak web), test vedle.
- `styles/architecture-landing.css`, předpona `arch-landing`.
