# Design: stránka v celku (vrstva 1)

Pohled **Design** vrstvy 1 Layout (`docs/navrhy/2026-11-10-platno-2.md`, Verze 6). `layout-canvas/LayoutCanvas` ho vykreslí místo mřížky, když `look="design"`.

- `components/DesignPage.tsx`: boxy nejvyšší úrovně jako tok stránky shora dolů. Výřez boxu (`covers`, první obrázek inspirace ze skenu) je `<img>` celý, v plné šířce boxu a ve svém poměru stran, bez ořezu; mezi boxy spára 3 px. Název a role jsou malý štítek v rohu (při najetí a u vybraného boxu výraznější). Box bez obrázku je kompaktní karta s popisem vzhledu `look` (jinak název). Rodič s obrázkem ukáže jen svůj obrázek (obsahuje i děti); bez obrázku se děti kreslí stejným tokem uvnitř. Klik vybere (`onSelectBox`), dvojklik otevře zanořený pohled (`onOpenBox`). Tah a změna velikosti tu nejsou; věta nad papírem říká, že rozmístění se mění v pohledu Layout.
- `logic/page-flow.ts` (test vedle): `pageFlow(boxes)` seskupí sourozence do řádků (překrývající se rozsah y) a v řádku do sloupců (překrývající se rozsah x, boxy nad sebou), s prázdnými sloupci `gaps` / `rest`; šířka v řádku je úměrná `w`/12.
- `styles/design-page.css`, předpona `design-page`.

Dílek nic nečte ani neukládá.
