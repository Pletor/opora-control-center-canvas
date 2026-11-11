# Boxy layoutu

Dílek levého panelu plátna 2 ve vrstvě **1 Layout** (`docs/navrhy/2026-11-10-platno-2.md`): deset boxů (Hlavička, Navigace, Sekce, Článek, Boční panel, Patička, Výzva, Formulář, Galerie, Obsah) a tři šablony (Klasický web, Landing, Aplikace). Data boxů a šablon jsou v `layout-canvas/logic/layout-templates.ts`.

- `components/BoxPalette.tsx`: klik hlásí `onAdd(box)` (box na konec stránky), stisk `onCarry(box, event)` začne tah na plátno, šablona `onTemplate(id)` (rodič se u neprázdného layoutu zeptá). Nic neukládá.
- `styles/box-palette.css`, předpona `box-palette`; tón čipu odpovídá barvě role boxu na plátně.
