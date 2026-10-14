# Přehled domén (Mapy architektury)

První obrazovka editoru architektury: řádek Produkce a řádek Vývoj, v každém karty domén s ikonou druhu (web / aplikace / administrace), hostem, „druh · účel“, tichým čipem ID (`ui-kit/copy-id`, plné ID v bublině, klik zkopíruje) a odkazem **Otevřít mapu domény**. Zachovává formulář domény a oddělení hostu ze starší sdílené struktury.

- `components/ArchitectureLanding.tsx` skládá dílky a drží rozepsaný formulář a potvrzení oddělení; ukládání jde callbackem do `ArchitectureEditor`.
- `components/DomainCard.tsx`, `DomainKindIcon.tsx`, `SplitConfirm.tsx` dostávají hotová data v props. `DomainCard` s `live` ukáže žeton webu a `DomainWork` (věta s počty, rozbalí stěsnaný strom worktree z `live-status/`; klidná doména nabídne „Nový worktree“). Zastaralý údaj nese „údaj z 12:03, nepodařilo se obnovit“.
- Pod větou hlavičky je jedna tichá řádka, jak práce začíná („1) Nový worktree na doméně → 2) Nová relace → 3) karta“), jen u projektů s worktree.
- Hlavička ukazuje souhrn hlavních relací („nenačteno“, dokud stav práce nepřišel) a „Nová hlavní relace“; když první čtení stavu práce nebo webu selže, řekne to věta pod hlavičkou. Worktree bez domény jsou ve skupině **Nepřiřazené**. Živá data dodá `ArchitectureEditor` (`LandingLive`).
- `components/DomainLockNote.tsx`: věta, proč jsou úpravy domén (a v Editoru stránky obsahu) zakázané; `ArchitectureEditor` ji ukazuje pod hlavičkou na všech třech obrazovkách, „+ Doména“ nese stejný důvod v `title`.
- `components/UnassignedWorktrees.tsx` + `AssignDomainRow.tsx`: skupina Nepřiřazené se stromem a u každého worktree „Přiřadit k doméně“ (výběr z `logic/domain-choices.ts`). Chyba backendu (i 404/405, když endpoint ještě neběží) se ukáže u řádku.
- `components/ArchiveShelf.tsx`: sbalené **Skladiště** na konci přehledu (aktér · krátké ID, doména, důvod, datum; větev v bublině), jen ke čtení, načte se při prvním rozbalení.
- `logic/domain-choices.ts`: domény s jedním hostem pro výběr („Produkce · www.example.cz“) a popisek domény ve skladišti, test vedle.
- `logic/domain-kind.ts` odvozuje druh z hostu (`app.` / `admin*` / jinak web), test vedle.
- `styles/architecture-landing.css`, předpona `arch-landing`.
