Záložky módů plátna uvnitř Editoru (struktura, text, kreslení, mapa); módy bere z shared/surface-settings. Kontrakt rozvržení: `docs/rozvrzeni-editoru.md` (Dílek 1); ikony: `docs/panely-editoru.md` (doladění bod 4). Název složky zůstává, i když to už není svislá lišta.

`ModeRail` kreslí **vodorovnou řadu záložek** na začátku lišty nástrojů Editoru (`.environment-toolbar.v3-toolbar` v `app/components/App.tsx`), hned před přepínači panelů (`layout/panel-dock/`). Každá záložka je ikona 16px vlevo od popisku 13px / 600 (`mode-rail__glyph`, `mode-rail__label`). Uvnitř `mode-rail__glyph` stojí dílek `<Icon size={16}>` ze sady `ui-kit/icon/`; jméno ikony k id módu vrací `logic/mode-rail.ts` (`modeIcon`, test vedle): structure → `layout-grid`, text → `type`, drawing → `pencil`, map → `map`. Neznámé id dostane `layout-grid`, aby lišta nikdy nezůstala prázdná.

Aktivní mód má modifikátor `mode-rail__button--active`, `aria-pressed="true"`, barvu `--accent` a spodní linku 2px. `aria-label` („Mód: …“) i `title` („jméno: nápověda“) nesou jméno módu, takže pod 1100px šířky okna, kdy se popisky skryjí jen vizuálně, zůstane jméno čitelné pro odečítač i v bublině.

Props: `{ mode, onMode, editorOnly? }`. Tlačítko Knihovna, props `libraryExpanded` a `onLibrary` i konstanta `LIBRARY_ICON` se zrušily — Knihovnu otevírá menu ☰ v `layout/panel-dock/` (`MenuButton`).

Styl drží blok `.mode-rail` v `layout/shell/styles/workspace-modes.css`. Lišta nástrojů kreslí stisknutá tlačítka jako pilulku (`.v3-toolbar button[aria-pressed]` v design-tokens); aktivní záložka ji přebíjí vlastním silnějším selektorem, aby zůstala jen barva a linka.
