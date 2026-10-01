Menu Editoru za jedním tlačítkem ☰: lišta ikon u levého okraje pracovní plochy a vedle ní panel zvolené sekce (Knihovna, Agenti, Postupy, Nastavení). Kontrakt je `docs/menu-a-katalog.md` (část A); profil a filtr katalogu `docs/suplik-a-profil.md` — kód je provádí, nemění. Nahradilo dvě tlačítka za záložkami módů (`PanelToggles`) a segmentový přepínač v šuplíku; obojí je smazané.

**Dílky**

- `components/MenuButton.tsx` — ☰ v liště nástrojů před záložkami módů: `aria-label="Menu Editoru"`, `aria-expanded`, `data-panel-anchor="menu"`, `data-testid="dock-menu"`. Props `{ open, onToggle }`; nic nedrží.
- `components/PanelDock.tsx` — rodič: skládá `DockRail` a (jen s otevřenou sekcí) `PanelDrawer`, obsah sekce dostane v `children`, hlavičku projektu v `head`. Drží jediné chování: `pointerdown` mimo rám pracovní plochy a mimo `[data-panel-anchor]` volá `onClose` (klik do horní lišty zavře, klik na plátno ne). Props `{ section, head, onSelect, onClose, children }`.
- `components/DockRail.tsx` — lišta 56 px přes celou výšku rámu: Knihovna, Agenti, Postupy, oddělovač, Nastavení. Ikony mají `aria-label`, `title` (se zkratkou) a `aria-pressed`; `data-testid="dock-section-<sekce>"`. Klik hlásí `onSelect`.
- `components/PanelDrawer.tsx` — panel sekce `section#panel-dock.panel-drawer` (`left: 56px`, šířka 380 px, pod 900 px šířky okna zbytek šířky), jediná hlavička panelu (název sekce + zkratka, žádný křížek), pod ní `head` a tělo. Při tažení položky dostane v dalším snímku `panel-drawer--dragging` (průhlednost 0.4, `pointer-events: none`), aby šlo pustit i na plátno pod ním; `dragend`/`drop` na `document` modifikátor sundá. Tělo má dole 52 px volna kvůli rohu účtu.
- `components/DockIcon.tsx` — ikona lišty: ze sady `ui-kit/icon`, nebo vlastní značky `menu` (☰) a `settings` (posuvníky) stejnou stopou.
- `components/DockSettings.tsx` — sekce Nastavení: karta profilu (`profileCard`, vždy rozbalená) a filtr katalogu `CatalogScopeBar` bez čísel s větou, co filtr dělá.
- `components/CatalogScopeBar.tsx` — pilulky „Pro tento projekt N“ / „Vše M“ (`data-testid="catalog-scope-<scope>"`); čísla jsou volitelná (v Nastavení nejsou).
- `components/CatalogOutsideRow.tsx` — čárkovaný řádek „Mimo profil: K prvků (…) · zobrazit / skrýt“ na konci seznamu (`data-testid="catalog-outside"`).

**Logika**

- `logic/panel-dock.ts` (+ test) — `DockSection` (`library | agents | flows | settings`), `DOCK_SECTIONS`, stav `{ rail, section, last }` a přechody: `toggleMenu` (☰ otevře lištu i s poslední sekcí; otevřené menu zavře celé), `selectSection` (neaktivní ikona přepne, aktivní sbalí panel a lišta zůstane), `shortcutSection`, `dismissDock` (Esc: nejdřív panel, pak lišta), `sectionForShortcut` (Ctrl+Shift+, Knihovna, Ctrl+Shift+. Agenti), `isDismissKey`. Poslední sekce se ukládá jednou pro aplikaci pod `opora:panel-dock:v1` jako `{ section }` (`parseDockSection`, `readDockSection`, `writeDockSection`); otevřenost se neukládá, po načtení stránky je menu zavřené.
- `logic/use-panel-dock.ts` — `usePanelDock(enabled)` → `{ rail, section, toggleMenu, select, close }`; jeden posluchač `keydown` pro zkratky a Esc (ne při psaní do pole). Mimo Editor menu zavře.
- `logic/panel-drawer.ts` (+ test) — `catalogView(items, profile, {scope, showOutside, query}, search)` rozdělí katalog podle profilu a vrátí `shown`, `hidden`, `outside`, `fittingCount`, `allCount`, `filtering`; `fitNote`, `profileOnlyGroup`; volba filtru pod `opora:panel-drawer:v1`.
- `logic/use-panel-drawer.ts` — `usePanelDrawer()` → `{ scope, setScope, showOutside, toggleOutside }`. Filtr se ukládá app-globálně, „mimo profil“ je jen paměť sezení.

**Styl**

`styles/panel-dock.css`, bloky `dock-menu`, `panel-dock`, `dock-rail`, `panel-drawer`, `dock-settings` a `catalog-scope`, BEM, každý s příběhovým komentářem, barvy jen z tokenů (světlý i tmavý režim).

**Zapojení**

`app/components/App.tsx` volá `usePanelDock`, `usePanelDrawer` a `useProjectProfile` (z `layout/project-profile/`) a profil spočítá přes `catalogProfile` z `shared/project-capabilities`. `MenuButton` stojí v liště nástrojů před `ModeRail`. V `.editor-frame` za `workspace-shell` stojí `<PanelDock>` jen v Editoru a jen s vysunutou lištou. `head` je `<ProjectProfile>` (mimo Nastavení; odkaz „Nastavit“/„Změnit“ volá `dock.select("settings")`), obsah je `LibraryNavbar`, `AgentNavbar` se `section="agents"` nebo `"flows"`, nebo `DockSettings` s `ProfileCard`.
