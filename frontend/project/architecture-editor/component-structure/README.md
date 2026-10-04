# Hierarchický editor komponenty

Třetí sloupec Editoru stránky (`docs/architektura-projektu.md`, krok 3). Ukazuje vybraný prvek (`rootId`) zevnitř: drobečky, „<název> · vnitřní struktura“, oblasti → sektory → uzly se stavem, pod tím **Workflow uživatele** a **Pipeline práce**.

- `components/ComponentStructure.tsx` skládá dílky `StructureArea` → `StructureSector` → `StructureTile` a `StructureFlows`; `StructureIcon` jsou inline SVG ikony (sdílí je i `element-detail`).
- `logic/structure-model.ts` (test vedle): `buildStructure` seskupuje přímé děti rootu **geometricky** přes `areaOf` (nikdy přes `parentId`); děti mimo oblast tvoří implicitní skupinu bez rámu. Sektor nemá vlastní vrstvu, bere nejčastější `card.layer` svých uzlů. Stav: uzavřeno → Hotovo, fáze build/verify → V řešení, jinak Čeká. `workflowChain` řadí potomky rootu topologicky podle vazeb `next` (vazba bez portu = `next`), uzly v cyklu dává na konec. `breadcrumbs` vede od nejvyššího předka po vybraný prvek pod rootem (jinak po root).
- Dílek nic neukládá. Klik na uzel = `onSelect`, dvojklik a drobečky = `onOpen`, `← Zpět na mapu` = `onClose`.
- `onAddNode(sectorId)` dostává skutečného rodiče. `onAddSector(id)` dostává **id oblasti** (sektor patří do oblasti geometricky, jeho rodičem je `area.parentId`) nebo `rootId` pro skupinu mimo oblast. `onAddArea(rootId)`.
