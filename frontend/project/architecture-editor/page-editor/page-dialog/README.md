# Nová stránka

Vyskakovací okno pro **+ Stránka** a **+ Podstránka** ve Struktuře plátna 2 (`docs/navrhy/2026-11-10-platno-2.md`): jen Název (povinný, fokus po otevření), Adresa (cesta předvyplněná z názvu, u podstránky pod cestou rodiče, dokud ji člověk nepřepíše) a Účel jednou větou (`site.goal`, nepovinný). Uložit / Zrušit, Esc zavře.

- `components/PageDialog.tsx`: nativní `<dialog>` (`showModal`), uložení hlásí `onSave(draft)` (`ProjectTree` → `ArchitectureEditor.saveProduct` → `sitePlan` přes `/api/canvas-plan`); chyba zůstane v okně. Úpravu existující stránky (✎) dál dělá plný formulář `domain-site/components/ArchitectureProductForm`.
- `logic/page-path.ts` (test vedle): `pathFromName(name, parentPath)`.
- `styles/page-dialog.css`, předpona `page-dialog`.
