Zavěšené panely Editoru: Knihovna a Agenti a postupy nevisí jako sloupce vedle plátna, ale jako karta 360px pod svým tlačítkem v liště nástrojů. Kontrakt je `docs/rozvrzeni-editoru.md` (Dílek 2) — kód ho provádí, nemění.

**Dílky**

- `components/PanelToggles.tsx` — dvě tlačítka hned za záložkami módů (`layout/mode-rail/`): ikona 16px, jméno a `kbd` se zkratkou. Otevřené tlačítko má modifikátor `panel-toggles__button--open`, `aria-expanded` a `aria-controls="panel-dock"`. Každé tlačítko nese `data-panel-anchor=<panel>` — podle něj dropdown najde, pod čím visí. Props `{ open, onToggle }`; nic nedrží.
- `components/PanelDropdown.tsx` — rám `section#panel-dock.panel-dock` absolutně v `.editor-frame` (`top/bottom: 8px`, šířka 360px). Obsah (Knihovnu nebo Agenty) dostane v `children` a nic o něm neví. Props `{ panel, label, onClose, children }`. Dělá tři věci:
  - **Poloha:** při připojení, při změně `panel` a při `resize` okna změří kotvu `[data-panel-anchor=<panel>]` a rám (rodič dropdownu), zavolá `dropdownPlacement` a zapíše `style.left` a proměnnou `--panel-dock-arrow` (střed šipky od levé hrany panelu).
  - **Zavření:** `pointerdown` mimo dropdown a mimo `[data-panel-anchor]` (v zachytávací fázi, aby ho nevzal dílek, který událost zastaví) volá `onClose`. Esc a zkratky drží hook, přepnutí módu a odchod z Editoru řídí App.
  - **Tažení:** po `dragstart` uvnitř dostane v dalším snímku (`requestAnimationFrame`) modifikátor `panel-dock--dragging` (průhlednost 0.4, `pointer-events: none`), aby šlo položku pustit i na plátno pod panelem. `dragend` nebo `drop` na `document` modifikátor sundá; panel po puštění zůstává otevřený.

**Logika**

`logic/panel-dock.ts` je čistá logika s testem vedle (`panel-dock.test.ts`, běží `npm test`):

- `DockPanel = "library" | "agents"` a `DOCK_PANELS` — pořadí, jméno, ikona (`library`, `bot`) a zkratka (`Ctrl+Shift+,`, `Ctrl+Shift+.`).
- `togglePanel(open, panel)` — tentýž panel zavře, jiný otevře místo něj; otevřený je nejvýš jeden.
- `panelForShortcut(event)` — znovupoužije `isLibraryCollapseShortcut` (`layout/library-navbar/logic/library-navbar.ts`) a `isCollapseShortcut` (`layout/agent-navbar/logic/agent-navbar.ts`).
- `isDismissKey(event)` — jen `Escape`.
- `PANEL_WIDTH = 360`, `PANEL_GAP = 8`, `ARROW_INSET = 44`, `ARROW_EDGE = 16` a `dropdownPlacement(anchorCenter, frameWidth)`: `left = clamp(anchorCenter − 44, 8, max(8, frameWidth − 368))`, `arrow = clamp(anchorCenter − left, 16, 344)`.

`logic/use-panel-dock.ts` je vazba na React: `usePanelDock(enabled)` vrací `{ open, toggle, close }`. Stav je **jen v paměti sezení** — neukládá se, takže po načtení stránky panel nikdy nezakrývá plátno. Jeden posluchač `keydown` na `window`: když je `enabled` a cíl není psací pole (`isTypingTarget` z `editor/canvas/history/logic/undo-shortcut`), zkratka panel přepne a Esc ho zavře. Když `enabled` přejde na `false`, panel se zavře.

**Styl**

`styles/panel-dock.css`, bloky `panel-toggles` a `panel-dock`, BEM, každý blok s příběhovým komentářem. Panel: povrch `--surface`, rámeček `--line-strong`, rádius 10px, stín `0 18px 48px` s neprůhledností 18 %, `overflow: visible` (z Knihovny vyčnívá sloupec náhledů), `z-index: 20` — nad plátnem i šuplíkem knihovny uzlu (6/7), pod horní lištou (30) a rohem účtu (60). Šipka `panel-dock__arrow` je čtvereček 12 × 12 otočený o 45° na horní hraně, `left: calc(var(--panel-dock-arrow) − 6px)`. Otevřené tlačítko: podklad `--accent-soft`, text `--accent`, rámeček `--accent-line`.

**Zapojení**

`app/components/App.tsx` volá `usePanelDock(environment === "editor" && screen === "canvas")` jednou před časnými návraty. Řada 2 (`.environment-toolbar.v3-toolbar`) začíná `<ModeRail/>` a `<PanelToggles/>`, za nimi `span.v3-grow` a skupiny nástrojů. V `.editor-frame` za `workspace-shell` stojí `<PanelDropdown>` jen v Editoru a jen s otevřeným panelem; uvnitř je `LibraryNavbar` nebo `AgentNavbar`, oba s `onClose={dock.close}`. `setMode` volá `dock.close()`.
