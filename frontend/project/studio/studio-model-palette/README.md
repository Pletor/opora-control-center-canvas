# Studio · MODEL · katalog

Levý panel vrstvy MODEL (`docs/studio.md` §3, etapa S6a): typy komponent z katalogu S4 ve skupinách Web, Data, Control,
Event, Deployment, Adapter, hledání a sbalitelné skupiny. Klik přidá komponentu na volné místo, přetažení na místo
puštění; samotné přidání (`createNode` + `withSimulationDefaults`) dělá rodič. Řízený Pod se samostatně nenabízí.

- `components/ModelPalette.tsx` (hledání, sbalení), `components/PaletteGroup.tsx` (skupina a položky, drag and drop).
- `logic/palette-groups.ts` – skupiny, hledání, souhrn portů, typ přetahovaných dat (`PALETTE_DRAG_TYPE`).
- `styles/studio-model-palette.css`, blok `studio-model-palette`.
