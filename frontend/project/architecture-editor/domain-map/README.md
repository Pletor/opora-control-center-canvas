# Mapa projektu (jedna doména)

Druhá obrazovka editoru architektury a jediné místo, kde se mění struktura: stránky, podstránky, pořadí, navigace. Vlevo panel domény (prostředí · projekt, host, účel, ID, **+ Přidat stránku**, seznam stránek s ID), vpravo NAVBAR a karty stránek s podstránkami.

- `components/ArchitectureDomainMap.tsx` skládá dílky a drží rozepsaný formulář a přesun; ukládání a mazání jde callbacky do `ArchitectureEditor`.
- `components/DomainPanel.tsx` (levý panel), `PageCard.tsx` (rekurzivní karta stránky), `MovePageForm.tsx` (přesun pod jiného rodiče).
- `components/ArchitectureProductForm.tsx` je formulář domény a stránky, používá ho i přehled domén (`landing/`).
- `styles/domain-map.css`, předpona `domain-map`.
