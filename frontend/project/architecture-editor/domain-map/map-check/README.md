# Díry mapy (kontrola mapy na mapě domény)

Panel **Díry mapy** nad cestami zákazníka na Mapě domény. Ukazuje výsledek kontroly mapy z backendu (`GET /api/project-architecture/map-check`, kontrakt `docs/architektura-pro-agenty.md` §5) jen pro otevřenou doménu: skupina na pravidlo s českým popiskem, počtem a krátkou radou, sbalitelný seznam zpráv backendu. Bez nálezů jen „Mapa je bez děr.“

- `components/MapCheckPanel.tsx` dostane hotové skupiny v `groups` a klik na zprávu hlásí `onSelect(target)`; nic nečte ani neukládá. Nález, který v grafu nemá místo (komponenta mimo stránku, smazaný uzel), je jen text.
- `logic/map-check.ts` (test vedle): `mapCheckUrl`, `normalizeMapCheck` (neznámá pravidla a vadné položky zahodí, nikdy nehodí výjimku), `MAP_CHECK_TEXT` (popisek a rada pravidla), `mapCheckGroups` (nálezy domény v pořadí `MAP_CHECK_RULES` = `RULES` backendu; uzel a hrana podle předků, cesta podle `site.journeys` domény) a `mapCheckTarget` (cíl kliku: stránka, komponenta s nejbližší stránkou, cesta, hrana se stránkou a uzlem zdroje).
- Čte `logic/use-map-check.ts` v `ArchitectureEditor` znovu při změně otisku grafu; skupiny spočítá rodič a předá přes `ArchitectureDomainMap` (`mapCheck`). Klik: stránka → `onOpen` (Editor stránky), komponenta → Editor její stránky s vybranou komponentou, hrana → Editor stránky zdroje s vybraným zdrojem (Vazby v Detailu prvku), cesta → editor cesty v **Cestách zákazníka** (stejná jednorázová žádost `initialJourneyId` jako z úseku cesty).
- `styles/map-check.css`, předpona `map-check`.
