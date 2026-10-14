# Mapa projektu (jedna doména)

Druhá obrazovka editoru architektury a jediné místo, kde se mění struktura: stránky, podstránky, pořadí, navigace. Vlevo panel domény (prostředí · projekt, host, účel, ID, **+ Přidat stránku**, seznam stránek s ID), vpravo NAVBAR a karty stránek s podstránkami.

- `components/ArchitectureDomainMap.tsx` skládá dílky a drží rozepsaný formulář a přesun; ukládání a mazání jde callbacky do `ArchitectureEditor`.
- `components/DomainPanel.tsx` (levý panel), `PageCard.tsx` (rekurzivní karta stránky s odznakem „N worktree“ a zvýrazněním stránek vybraného worktree, `PageWork`), `MovePageForm.tsx` (přesun pod jiného rodiče).
- Slot `live` = pravý sloupec (`LiveDomainPanel` z `live-status/`); s ním má rozvržení tři sloupce, pod 1050 px sjede panel pod mapu.
- `components/ArchitectureProductForm.tsx` je formulář domény a stránky, používá ho i přehled domén (`landing/`).
- `styles/domain-map.css`, předpona `domain-map`.
