# Přehled domén (Mapy architektury)

První obrazovka editoru architektury: řádek Produkce a řádek Vývoj, v každém karty domén s ikonou druhu (web / aplikace / administrace), hostem, „druh · účel“, ID a odkazem **Otevřít mapu projektu**. Zachovává formulář domény a oddělení hostu ze starší sdílené struktury.

- `components/ArchitectureLanding.tsx` skládá dílky a drží rozepsaný formulář a potvrzení oddělení; ukládání jde callbackem do `ArchitectureEditor`.
- `components/DomainCard.tsx`, `DomainKindIcon.tsx`, `SplitConfirm.tsx` dostávají hotová data v props. `DomainCard` s `live` ukáže žeton webu a `DomainWork` (věta s počty, rozbalí stěsnaný strom worktree z `live-status/`; klidná doména nabídne „Nový worktree“). Zastaralý údaj nese „údaj z 12:03, nepodařilo se obnovit“.
- Hlavička ukazuje souhrn hlavních relací („nenačteno“, dokud stav práce nepřišel) a „Nová hlavní relace“; když první čtení stavu práce nebo webu selže, řekne to věta pod hlavičkou. Worktree bez domény jsou ve skupině **Nepřiřazené**. Živá data dodá `ArchitectureEditor` (`LandingLive`).
- `logic/domain-kind.ts` odvozuje druh z hostu (`app.` / `admin*` / jinak web), test vedle.
- `styles/architecture-landing.css`, předpona `arch-landing`.
