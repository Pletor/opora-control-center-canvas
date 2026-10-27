# Pruh navigace domény

Řádek nad plátnem Editoru stránky (`PageEditor`): stejné hlavní stránky, ve stejném pořadí a se stejným popiskem (`navLabel`, jinak název) jako NAVBAR na Mapě domény. Pod ním druhá řada s podstránkami aktivní větve (odsazené podle hloubky). Otevřená stránka svítí (`aria-current="page"`), její předek obrysem. Klik hlásí `onOpen(pageId)`; `PageEditor` ho pošle do `onOpenPage` rodiče, tedy stejnou navigací jako klik ve Stromu projektu (`ArchitectureEditor.openPage` → `navigate`). Aktivní stránka je otevřený rozsah, žádný druhý stav.

- `components/PageNav.tsx`: tlačítka v seznamu (ovladatelné klávesnicí), `<nav aria-label="Navigace domény">`. Nic neukládá.
- `logic/page-nav.ts` (test vedle): `pageNav(pages, activePage)` nad `domainPageTree` (pořadí z `graph.nodes`) a `navLabelOf` z `domain-map/logic/page-site.ts`.
- `styles/page-nav.css`, předpona `page-nav__`.
