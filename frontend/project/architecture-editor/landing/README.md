# Přehled domén (Mapy architektury)

První obrazovka editoru architektury: řádek Produkce a řádek Vývoj, v každém karty domén s ikonou druhu (web / aplikace / administrace), hostem, „druh · účel“, ID a odkazem **Otevřít mapu projektu**. Zachovává formulář domény a oddělení hostu ze starší sdílené struktury.

- `components/ArchitectureLanding.tsx` skládá dílky a drží rozepsaný formulář a potvrzení oddělení; ukládání jde callbackem do `ArchitectureEditor`.
- `components/DomainCard.tsx`, `DomainKindIcon.tsx`, `SplitConfirm.tsx` dostávají hotová data v props.
- `logic/domain-kind.ts` odvozuje druh z hostu (`app.` / `admin*` / jinak web), test vedle.
- `styles/architecture-landing.css`, předpona `arch-landing`.
