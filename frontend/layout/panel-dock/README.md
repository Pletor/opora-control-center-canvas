Menu Editoru za jedním tlačítkem ☰: lišta ikon u levého okraje pracovní plochy a vedle ní panel zvolené sekce. Sekce shora: **Struktura**, **Schránka**, pod oddělovačem **Nastavení**. Kontrakt je `docs/menu-a-katalog.md` (část A, rozvržení menu), sekci Schránka `docs/navrh-schranka-zadani.md` („Dvě stopy a levé menu“) — kód je provádí, nemění. Sekce Knihovna (Prvky), Agenti (Katalog, Kód) a Postupy jsou smazané; záložka Struktura Knihovny je teď sekce Struktura a záložka Vybraná karta Agentů je druhá záložka Struktury.

**Dílky**

- `components/MenuButton.tsx` — ☰ v liště nástrojů před záložkami módů: `aria-label="Menu Editoru"`, `aria-expanded`, `data-panel-anchor="menu"`, `data-testid="dock-menu"`. Props `{ open, onToggle }`; nic nedrží.
- `components/PanelDock.tsx` — rodič: skládá `DockRail` a panel otevřené sekce (`children`). Obsah, který se nesmí zničit (Schránka s rozepsaným textem), dostane v `kept` a drží ho v pevném místě DOM, skrytý při jiné sekci i při zavřeném menu (`rail={false}` → `panel-dock--closed`). Drží jediné chování: `pointerdown` mimo rám pracovní plochy a mimo `[data-panel-anchor]` volá `onClose`. Props `{ rail, section, onSelect, onClose, kept, children }`.
- `components/DockRail.tsx` — lišta 56 px: Struktura, Schránka, oddělovač, Nastavení. Ikony mají `aria-label`, `title` (se zkratkou) a `aria-pressed`; `data-testid="dock-section-<sekce>"`. Klik hlásí `onSelect`.
- `components/PanelDrawer.tsx` — panel sekce `section#panel-dock.panel-drawer` (`left: 56px`, šířka 380 px; sekce s `wide` (Schránka) `panel-drawer--wide` až 1100 px s pruhem plátna vpravo; pod 900 px šířky okna zbytek šířky), jediná hlavička (název sekce + zkratka) a tělo s 52 px volna dole kvůli rohu účtu. `kept` = skrytý držený panel (`panel-drawer--kept`, bez id a přístupného jména).
- `components/DockIcon.tsx` — ikona lišty: ze sady `ui-kit/icon`, nebo vlastní značky `menu` (☰), `settings` (posuvníky) a `vault` (přihrádka Schránky) stejnou stopou.
- `components/DockSettings.tsx` — sekce Nastavení: karta profilu projektu (`profileCard`, vždy rozbalená). Filtr katalogu „Pro tento projekt / Vše“ zmizel s katalogy.

**Logika**

- `logic/panel-dock.ts` (+ test) — `DockSection` (`structure | vault | settings`), `DOCK_SECTIONS` (příznak `wide`), stav `{ rail, section, last }` a přechody: `toggleMenu`, `selectSection` (neaktivní ikona přepne, aktivní sbalí panel a lišta zůstane), `openSection` (odkaz odjinud, např. čip „Ze schránky“, otevře lištu rovnou na sekci a nikdy ji nesbalí), `shortcutSection`, `dismissDock` (Esc: nejdřív panel, pak lišta), `sectionForShortcut` (**Ctrl+Shift+,** Struktura, **Ctrl+Shift+.** Schránka; na Macu ⌘, platí i „<“ / „>“, Alt zkratku vylučuje), `isDismissKey`. Poslední sekce se ukládá jednou pro aplikaci pod `opora:panel-dock:v1` jako `{ section }`; staré hodnoty `library`, `agents`, `flows`, `skeleton` se čtou jako `structure`. Otevřenost se neukládá.
- `logic/use-panel-dock.ts` — `usePanelDock(enabled)` → `{ rail, section, toggleMenu, select, open, close }`; jeden posluchač `keydown` pro zkratky a Esc (ne při psaní do pole). Mimo Editor menu zavře.

**Styl**

`styles/panel-dock.css`, bloky `dock-menu`, `panel-dock`, `dock-rail`, `panel-drawer` a `dock-settings`, BEM, každý s příběhovým komentářem, barvy jen z tokenů (světlý i tmavý režim).

**Zapojení**

`app/components/App.tsx` volá `usePanelDock` a `useProjectProfile` (z `layout/project-profile/`), profil spočítá přes `catalogProfile` z `shared/project-capabilities`. `MenuButton` stojí v liště nástrojů před `ModeRail`. V `.editor-frame` stojí `<PanelDock>` jen v Editoru, s vysunutou lištou nebo s drženou Schránkou. Obsah: `StructurePanel` (`layout/structure-panel/`, záložky Struktura | Vybraná karta, `CardBrief` z `layout/card-brief/`), `BriefVaultDock` v `kept` (`editor/brief-vault-dock/`, rozsah a fokus z `openVault`), nebo `DockSettings` s `ProfileCard`.
