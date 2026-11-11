# Struktura (strom stránek otevřené domény)

Levý panel plátna 2 nahoře. Projekce grafu (`domainPageTree`): jen otevřená doména, žádné skupiny prostředí ani jiné domény; stránky v uloženém pořadí s odsazenými podstránkami, aktivní stránka je zvýrazněná.

- `components/ProjectTree.tsx`: klik na stránku hlásí `onOpenPage(pageId)`. **+ Stránka** (v hlavičce) a **+ Podstránka** u stránky otevřou vyskakovací okno `page-dialog/` jen s Názvem, Adresou a Účelem jednou větou; ✎ otevře pod stromem plný formulář stránky `ArchitectureProductForm` (`domain-site/`: přejmenování, cesta, cíl, sekce). Rozepsané okno i formulář drží dílek, uložení jde přes `onSave` (rodič `saveProduct`, nová stránka se hned otevře). ↑ ↓ hlásí `onReorder` (prohození sourozenců, `reorderDomainPage`), ✕ `onRemove` (náhled a dialog odstranění u rodiče). Zámek struktury (`disabled`) vypne všechny úpravy.
- `logic/project-tree-model.ts` (test vedle): `structureRows` (řádky stromu s hloubkou, aktivní stránkou a prvním / posledním sourozencem), `activePageId`, `environmentOf`, `isSharedDomain` (vícehostová aplikace, kterou plátno 2 neotevře).
- `styles/project-tree.css`, předpona `project-tree`.
