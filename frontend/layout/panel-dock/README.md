Šuplík Editoru: Knihovna a Agenti a postupy vyjíždějí u levého okraje pracovní plochy jako pás 380px přes celou výšku pod lištou. Kontrakt je `docs/suplik-a-profil.md` (část 4) — kód ho provádí, nemění. Nahradil zavěšený panel pod tlačítkem (`PanelDropdown`, `dropdownPlacement` a šipka jsou smazané).

**Dílky**

- `components/PanelToggles.tsx` — dvě tlačítka hned za záložkami módů (`layout/mode-rail/`): ikona 16px, jméno a `kbd` se zkratkou. Otevřené tlačítko má modifikátor `panel-toggles__button--open`, `aria-expanded` a `aria-controls="panel-dock"`. Props `{ open, onToggle }`; nic nedrží.
- `components/PanelDrawer.tsx` — rám `section#panel-dock.panel-drawer` absolutně v `.editor-frame` (`left: 0; top: 0; bottom: 0; width: 380px`, pod 900px šířky okna 100 %), `z-index: 20`, pravá hrana s linkou a stínem do plátna. Nahoře segmentový přepínač Knihovna | Agenti a postupy (`data-testid="drawer-switch-<panel>"`, hlásí `onSelect`), pod ním `head` (hlavička projektu z `layout/project-profile/`) a pod tím `children`. Props `{ panel, onSelect, onClose, head, children }`.
  - **Zavření:** `pointerdown` mimo šuplík, mimo `[data-panel-anchor]` a mimo rám pracovní plochy volá `onClose`. Klik na plátno ani do inspektoru šuplík nezavře — šuplík je nezakrývá. Esc a zkratky drží hook, přepnutí módu a odchod z Editoru řídí App.
  - **Tažení:** po `dragstart` uvnitř dostane v dalším snímku modifikátor `panel-drawer--dragging` (průhlednost 0.4, `pointer-events: none`), aby šlo položku pustit i na plátno pod šuplíkem. `dragend` nebo `drop` na `document` modifikátor sundá; šuplík zůstává otevřený.
  - Tělo má dole 52px volna kvůli rohu účtu (tlačítko Opora leží nad vším vlevo dole).
- `components/CatalogScopeBar.tsx` — pilulky „Pro tento projekt N“ / „Vše M“ (`data-testid="catalog-scope-<scope>"`). Vykreslí je Knihovna i Agenti pod hledáním, jen když je profil nastavený.
- `components/CatalogOutsideRow.tsx` — čárkovaný řádek „Mimo profil: K prvků (…) · zobrazit / skrýt“ na konci seznamu (`data-testid="catalog-outside"`).

**Logika**

- `logic/panel-dock.ts` (+ test) — `DockPanel`, `DOCK_PANELS`, `togglePanel`, `panelForShortcut`, `isDismissKey`.
- `logic/use-panel-dock.ts` — `usePanelDock(enabled)` → `{ open, toggle, close }`, stav jen v paměti sezení; zkratky Ctrl+Shift+, / Ctrl+Shift+. a Esc.
- `logic/panel-drawer.ts` (+ test) — `catalogView(items, profile, {scope, showOutside, query}, search)` rozdělí katalog podle profilu (`splitByProfile` z `library-catalog/logic/catalog-fit.ts`) a vrátí `shown`, `hidden`, `outside`, `fittingCount`, `allCount`, `filtering`. Hledání jde vždy přes celý katalog. `fitNote` (poznámka „mimo profil“ / „kvůli profilu: …“), `profileOnlyGroup` (skupina jen kvůli profilu) a uložení volby filtru pod jediným klíčem aplikace `opora:panel-drawer:v1` (`parseCatalogScope`, `readCatalogScope`, `writeCatalogScope`).
- `logic/use-panel-drawer.ts` — `usePanelDrawer()` → `{ scope, setScope, showOutside, toggleOutside, editingProfile, setEditingProfile, profileDismissed, dismissProfile }`. Filtr se ukládá app-globálně, ostatní je jen paměť sezení („Teď ne“ platí do zavření stránky).

**Styl**

`styles/panel-dock.css`, bloky `panel-toggles`, `panel-drawer` a `catalog-scope`, BEM, každý s příběhovým komentářem, barvy jen z tokenů.

**Zapojení**

`app/components/App.tsx` volá `usePanelDock`, `usePanelDrawer` a `useProjectProfile` (z `layout/project-profile/`) a profil spočítá přes `catalogProfile` z `shared/project-capabilities`. V `.editor-frame` za `workspace-shell` stojí `<PanelDrawer>` jen v Editoru a jen s otevřeným panelem; `head` je `<ProjectProfile>`, uvnitř `LibraryNavbar` nebo `AgentNavbar` s `profile`, `scope`, `showOutside`, `onScope`, `onToggleOutside` a `onClose={dock.close}`.
