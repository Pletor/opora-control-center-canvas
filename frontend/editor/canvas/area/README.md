Oblast na plátně (`kind: "area"`): dashovaný rámeček, ne karta uzlu. Seskupuje karty geometricky —
karta patří do nejmenší oblasti na stejné vrstvě, jejíž obdélník obsahuje její střed (`x+136, y+120`;
komentář `x+120, y+80`) — členství se nikde neukládá, počítá se z pozic při každém vykreslení. Stejné
pravidlo počítá i backend (`backend/canvas/areas.py`, `area_of`) pro `context.area` / `graph.areaMembers`
/ `graph.areaFlows` v node-brief.

`components/AreaCard.tsx` je React Flow uzel typu `area` (bez knihovny, bez bloků): dashovaný obdélník
s tagem jména v levém horním rohu (dvojklik přejmenuje) a dvěma úchyty toku (`flow`, vpravo zdroj,
vlevo cíl) — vidět jen při hoveru nebo výběru. Velikost nese `style` uzlu, který nastavuje Board z
`data.view.w/h`; `NodeResizer` (viditelný jen vybraný) hlásí novou velikost přes `onResize`.
`components/AreaPanel.tsx` je jeho inspektor vpravo: jméno, účel, ke čtení seznam karet uvnitř (klik
otevře uzel) a toků do/z jiných oblastí, na konci smazání — to smaže jen uzel oblasti, členové zůstávají
(členství je geometrické, ne odkaz).

`logic/area-model.ts` (testováno) je čistý model bez Reactu: `isArea`, `newArea` (nepojmenovaná,
720×480), `areaLabel` (jméno nebo „Nepojmenovaná oblast“), `areaOf` / `membersOf` (stejné pravidlo jako
backend), `moveWithMembers` (posune oblast i její členy najednou při tažení rámečku), `resizeArea`
(ohraničí 120..20000) a `AREA_COLORS` / `areaColorOf` / `setAreaColor` (šest barev rámečku, ať jde
skupiny na plátně rozeznat od sebe; chybějící nebo neznámá hodnota je vždy indigová). Oblast nemá zdroj,
vazby `next/action/rule` ani děti a nikdy není rodičem ani členem jiné oblasti — vazby mezi oblastmi
vedou jen portem `flow` (dashovaná čára barvou `--area-line`). App a Board ji proto všude, kde staví
seznamy cílů odkazů, štítků nebo knihovny, vylučují stejně jako komentář.
