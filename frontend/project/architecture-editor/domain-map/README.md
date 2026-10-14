# Mapa domény (jedna doména)

Druhá obrazovka editoru architektury a jediné místo, kde se mění struktura: stránky, podstránky, pořadí, navigace. Vlevo panel domény (prostředí · doména, host s čipem ID z `ui-kit/copy-id`, účel, **+ Přidat stránku**, seznam stránek s cestou, ID v bublině), vpravo NAVBAR a karty stránek s podstránkami.

- `components/ArchitectureDomainMap.tsx` skládá dílky a drží rozepsaný formulář a přesun; ukládání a mazání jde callbacky do `ArchitectureEditor`.
- `components/DomainPanel.tsx` (levý panel), `PageCard.tsx` (rekurzivní karta stránky s odznakem „N worktree“ a zvýrazněním stránek vybraného worktree, `PageWork`), `MovePageForm.tsx` (přesun pod jiného rodiče).
- Slot `live` = pravý sloupec (`LiveDomainPanel` z `live-status/`, jen u projektů s worktree); s ním má rozvržení tři sloupce, pod 1050 px sjede panel pod mapu jako nízký pruh (nejvýš 40 % výšky, web a worktree vedle sebe) a do 760 px je jeden sloupec s živým souhrnem nahoře. Bez slotu dostane levý panel jen žeton webu (`webBadge`).
- `components/ArchitectureProductForm.tsx` je formulář domény a stránky, používá ho i přehled domén (`landing/`).
- `styles/domain-map.css`, předpona `domain-map`.
