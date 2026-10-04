Editor jednoho bloku v levé zásuvce (`BlockEditor`): název, popis, porty (`BlockPortsEditor`), stav
a větvení, štítky, checklist a obrázky (přebráno ze záložky Strom - `BlockState`, `BlockTags`, `BlockTodos`,
`BlockImages`) a seznam podbloků s přepnutím na ně. Obal `BlockEditorDrawer` se otevře jen při explicitním
výběru konkrétního bloku. Výběr samotného uzlu levý panel neotevírá; zavření editoru vrátí výběr na uzel.

Události skládá `logic/block-events.ts`: `blockEvents` (sdílené jádro pro Strom i Editor) a `blockEditorEvents`
(totéž plus porty a klik na podblok). Dílek sám nic neukládá - `events` jen zabalují mutace z
`node-detail/tree/logic/tree-model.ts` a posílají je přes `run`/`desktop.mutate`. Ukládá ten, kdo drží stav
Desktop v3: záložka Strom (`NodeTree`), nebo `App.tsx` / `BlockDrawerContent.tsx` pro tuto zásuvku.
