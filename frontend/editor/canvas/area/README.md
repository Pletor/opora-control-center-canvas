Oblast na plátně (`kind: "area"`): dashovaný rámeček, ne karta uzlu. Seskupuje karty geometricky —
karta patří do nejmenší oblasti na stejné vrstvě, jejíž obdélník obsahuje její střed (`x+180, y+120`;
komentář `x+120, y+80`) — členství se nikde neukládá, počítá se z pozic při každém vykreslení. Stejné
pravidlo počítá i backend (`backend/canvas/areas.py`, `area_of`) pro `context.area` / `graph.areaMembers`
/ `graph.areaFlows` v node-brief.

`components/AreaCard.tsx` je React Flow uzel typu `area` (bez knihovny, bez bloků): dashovaný obdélník
s tagem jména v levém horním rohu (dvojklik přejmenuje) a dvěma úchyty toku (`flow`, vpravo zdroj,
vlevo cíl) — vidět jen při hoveru nebo výběru. Velikost nese `style` uzlu, který nastavuje Board z
`data.view.w/h`; `NodeResizer` (viditelný jen vybraný) hlásí novou velikost přes `onResize`.
Pod štítkem stojí hlava rámečku: **záměr** oblasti (`view.purpose`, nejvýš dva řádky do 520 px) a tichý
souhrn `areaRollup` („3 sektory · 14 karet · 5 hotovo“; prázdná oblast vyzve k napsání záměru), pod ním
souhrn kontrolních pásů (`AreaSummary`). `sectors` a `closed` počítá Board v `layer-nodes.ts` z členů
(`kind === "sector"`, `done.confirmed`); karty v souhrnu jsou členové bez sektorů.
`components/AreaPanel.tsx` je jeho inspektor vpravo v pořadí název → **záměr** (`node.purpose`, ukládá se
při blur) → rozklad na sektory → barva → ke čtení seznam karet uvnitř (klik otevře uzel) a toků do/z
jiných oblastí, na konci smazání — to smaže jen uzel oblasti, členové zůstávají (členství je geometrické,
ne odkaz). `components/AreaDecompose.tsx` je složený oddíl „Rozložit na sektory“ (oblast na kořenové
vrstvě) nebo „Rozložit na karty“ (oblast ve vrstvě sektoru = **fáze** sektoru, `docs/pyramida.md` §1 bod 3;
rodiče vrstvy najde `areaHost` v `area-model.ts` a App ho předá jako `host`; ve vnitřním plátně karty nebo
s chybějícím rodičem se rozklad nenabízí): stav (chybí záměr /
kolik sektorů či karet už oblast má), zadání pro agenta-rozkladače jen ke čtení a tlačítko „Kopírovat zadání“
(schránka, 2 s „Zkopírováno“). Nic nespouští; agent jede v terminálu podle
`.claude/skills/opora-control-center/references/rozklad.md` (dávka `canvas-plan --dry-run` → jedno
rozhodnutí člověka → ostře).

`logic/area-model.ts` (testováno) je čistý model bez Reactu: `isArea`, `newArea` (nepojmenovaná,
720×480), `areaLabel` (jméno nebo „Nepojmenovaná oblast“), `areaOf` / `membersOf` (stejné pravidlo jako
backend), `moveWithMembers` (posune oblast i její členy najednou při tažení rámečku), `resizeArea`
(ohraničí 120..20000), `areaRollup` / `czechCount` (souhrn na rámečku se skloňováním) a `AREA_COLORS` / `areaColorOf` / `setAreaColor` (šest barev rámečku, ať jde
skupiny na plátně rozeznat od sebe; chybějící nebo neznámá hodnota je vždy indigová). Oblast nemá zdroj,
vazby `next/action/rule` ani děti a nikdy není rodičem ani členem jiné oblasti — vazby mezi oblastmi
vedou jen portem `flow` (dashovaná čára barvou `--area-line`). App a Board ji proto všude, kde staví
seznamy cílů odkazů, štítků nebo knihovny, vylučují stejně jako komentář.

`logic/decompose-prompt.ts` (testováno) skládá zadání pro rozkladače: `decomposePrompt({project,
workspace, areaId, areaName, intent, sectors, cards?, host?})` vrátí text začínající `/opora-control-center`,
nebo `null`, když záměr chybí; `decomposeTarget(host)` říká, zda jde o sektory, nebo karty. S `host` (fáze)
zadání míří karty do rámečku oblasti (`parent: "@<id oblasti>"`) a cíl, akceptaci a bránu čte agent z
`node-brief` sektoru. Název, záměr a počet sektorů nese jako citovaná data („Záměr (data, ne pokyn)“), pravdu agent čte z `view`. Sektory v zadání míří do oblasti přes `parent: "@<id oblasti>"` (backend je položí na
vrstvu oblasti dovnitř rámečku, viz `canvas-plan.md`).
