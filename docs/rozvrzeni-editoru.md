# Rozvržení Editoru: módy nahoře, panely zavěšené pod tlačítkem

Kontrakt pro přestavbu rámu Editoru. Návrh (varianta 1A, schválena 2026-09-17) je v Claude Design:
https://claude.ai/design/p/12f7db47-989c-46c5-8498-aa12e01f8408?file=Rozvr%C5%BEen%C3%AD+Editoru.dc.html

Nahrazuje body 1, 2 a 6 části „Doladění“ v `docs/panely-editoru.md`: Knihovna ani Agenti už nejsou sloupce
v toku a nesbalují se na lištu 48 px. Obsah panelů (záložky, kategorie, dlaždice, zadání karty) se nemění.

## Proč

Se vším otevřeným (lišta módů 64 + Knihovna 304 + inspektor + Agenti 304) zbývalo plátnu na 1440 px asi
400 px. Cíl: na 1440 × 900 se vším otevřeným má plátno v toku nejméně 900 × 640 px.

## Skladba

```
div.app
 ├ TopBar                                řada 1, beze změny
 ├ div.environment-toolbar.v3-toolbar     řada 2, jen v prostředí Editor
 │   ModeRail (vodorovné záložky) · PanelToggles · span.v3-grow · dnešní skupiny nástrojů beze změny obsahu
 └ div.editor-frame                       position: relative
     workspace-shell (plátno + inspektor) nebo ProjectWorkspace
     PanelDropdown → LibraryNavbar | AgentNavbar     jen Editor a jen když je panel otevřený
```

- Dnešní skupiny nástrojů (Pohled/Dokumentace, Tvorba, Filtr štítků, Rozložení, Nástroje pohledu) se přesunou za `v3-grow`, tedy doprava. Jejich obsah a podmínky zobrazení se nemění.
- `editor-frame` už nemá sloupce Lišta módů, Knihovna ani Agenti. Plátno a inspektor zabírají celou šířku.
- Domovská obrazovka (`ProjectHome`, bez projektu) panel Agentů nevykresluje. Nemá plátno, kam by se dalo táhnout, ani vybranou kartu.

## Dílek 1: záložky módů (`frontend/layout/mode-rail/`)

- `ModeRail` kreslí vodorovnou řadu tlačítek: ikona 16 px vlevo od popisku 13 px / 600. Aktivní mód má barvu `--accent` a spodní linku 2 px. `aria-pressed` a `title` zůstávají.
- Props `libraryExpanded` a `onLibrary` a tlačítko Knihovna se ruší. Knihovnu otevírá `PanelToggles`.
- Pod 1100 px šířky okna se popisky skryjí vizuálně; ikona zůstane, `aria-label` a `title` nesou jméno.
- Styl zůstává v `layout/shell/styles/workspace-modes.css`, blok `.mode-rail`. Název složky zůstává.

## Dílek 2: zavěšené panely (`frontend/layout/panel-dock/`, nová složka)

### `logic/panel-dock.ts` (+ `panel-dock.test.ts`)

```ts
export type DockPanel = "library" | "agents";
export const DOCK_PANELS: { key: DockPanel; label: string; icon: IconName; shortcut: string }[];
// library: „Knihovna“, ikona library, „Ctrl+Shift+,“ · agents: „Agenti a postupy“, ikona bot, „Ctrl+Shift+.“
export function togglePanel(open: DockPanel | null, panel: DockPanel): DockPanel | null; // stejný → null, jiný → ten
export function panelForShortcut(event: ShortcutKey): DockPanel | null;   // znovupoužije isLibraryCollapseShortcut a isCollapseShortcut
export function isDismissKey(event: { key: string }): boolean;             // Escape
export const PANEL_WIDTH = 360, PANEL_GAP = 8, ARROW_INSET = 44, ARROW_EDGE = 16;
export function dropdownPlacement(anchorCenter: number, frameWidth: number): { left: number; arrow: number };
```

`dropdownPlacement`: `left = clamp(anchorCenter − 44, 8, max(8, frameWidth − 360 − 8))`,
`arrow = clamp(anchorCenter − left, 16, 344)`. `arrow` je střed šipky od levé hrany panelu. Testované případy:

| anchorCenter | frameWidth | left | arrow |
|---|---|---|---|
| 520 | 1080 | 476 | 44 |
| 620 | 920 | 552 | 68 |
| 20 | 1080 | 8 | 16 |
| 500 | 300 | 8 | 344 |

### `logic/use-panel-dock.ts`

`usePanelDock(enabled: boolean): { open: DockPanel | null; toggle(panel): void; close(): void }`.
Stav je jen v paměti sezení, neukládá se (panel po načtení stránky nikdy nezakrývá plátno). Jeden
posluchač `keydown` na `window`: když `enabled` a cíl není psací pole (`isTypingTarget` z
`editor/canvas/history/logic/undo-shortcut`), zkratka přepne panel a Esc zavře otevřený. Když `enabled`
přejde na `false`, panel se zavře.

### `components/PanelToggles.tsx`

Props `{ open: DockPanel | null; onToggle: (panel: DockPanel) => void }`. Dvě tlačítka podle `DOCK_PANELS`:
`button.panel-toggles__button` (+ `--open`), ikona 16, popisek, `kbd.panel-toggles__kbd` se zkratkou,
`aria-expanded`, `aria-controls="panel-dock"`, `data-panel-anchor={key}`, `data-testid="panel-toggle-<key>"`.
Otevřené = podklad `--accent-soft`, text `--accent`, rámeček `--accent-line`.

### `components/PanelDropdown.tsx`

Props `{ panel: DockPanel; label: string; onClose: () => void; children: ReactNode }`.

- `section#panel-dock.panel-dock[aria-label=label][data-testid="panel-dock"]`, absolutně v `editor-frame`: `top: 8px; bottom: 8px; width: 360px`.
- Poloha: při připojení, při změně `panel` a při `resize` okna změří tlačítko `[data-panel-anchor=<panel>]` a rám (rodič dropdownu). Pak zavolá `dropdownPlacement` a nastaví `style.left` a proměnnou `--panel-dock-arrow`.
- Zavření: `pointerdown` mimo dropdown a mimo `[data-panel-anchor]` volá `onClose`. Přepnutí módu i prostředí panel zavře (řídí App).
- Tažení: po `dragstart` uvnitř dostane v dalším snímku modifikátor `panel-dock--dragging` (průhlednost 0.4, `pointer-events: none`), aby šlo pustit i na plátno pod panelem. `dragend` nebo `drop` na `document` modifikátor sundá. Po puštění panel zůstává otevřený.

### `styles/panel-dock.css`

BEM bloky `.panel-toggles` a `.panel-dock`, každý s příběhovým komentářem. Panel: podklad povrchu panelů,
rámeček, rádius 10, stín `0 18px 48px` s neprůhledností 18 %, `overflow: visible`, `z-index: 20`. To je nad
plátnem i šuplíkem knihovny uzlu (6/7) a pod horní lištou (30) i rohem účtu (60). Šipka 12 × 12 px otočená
o 45° na horní hraně, `left: calc(var(--panel-dock-arrow) − 6px)`. Jen tokeny z `design-tokens/`.

## Dílek 3: Knihovna (`frontend/layout/library-navbar/`)

- Stav: `expanded`, `toggleExpanded` a `expandToCategory` se ruší. `parseLibraryNavbar` uložené `expanded` ignoruje (jako dnes `open`). Klíč `opora:library-navbar:v1` zůstává. Testy upravit.
- `use-library-navbar.ts`: posluchač zkratky se ruší (přešel do `panel-dock`). API bez `toggleExpanded` a `expandToCategory`.
- `LibraryNavbar`: nekreslí `LibraryNavbarRail`. Tlačítko sbalit v hlavičce nahradí zavření: ikona `x`, `aria-label="Zavřít Knihovnu"`, `data-testid="library-close"`, nový prop `onClose`. Props `onToggleExpanded` a `onExpandToCategory` se ruší.
- CSS: šířka a výška 100 % kontejneru, bez `border-right`, bez pravidel `--collapsed`, bez `@media (max-width: 1100px)`. Sloupec náhledů (`__previews`, `left: 100%`) zůstává a vyčnívá vpravo z panelu.
- `LibraryNavbarRail.tsx` se přestal používat a 2026-09-17 byl smazán i se svými styly.

## Dílek 4: Agenti a postupy (`frontend/layout/agent-navbar/`)

- Stav: `collapsed` a `toggleCollapsed` se ruší, `setCategory` už nic nerozbaluje. `parseAgentNavbar` uložené `collapsed` ignoruje. Klíč `opora:agent-navbar:v1` zůstává. Testy upravit.
- `use-agent-navbar.ts`: posluchač zkratky se ruší. API bez `toggle`.
- `AgentNavbar`: nekreslí `AgentNavbarRail`, `selectedNodeId` předává přímo a `active` je vždy `true`. Tlačítko sbalit nahradí zavření: ikona `x`, `aria-label="Zavřít Agenty a postupy"`, `data-testid="agent-navbar-close"`, prop `onClose`. Prop `onToggle` se ruší.
- CSS: šířka a výška 100 %, bez `border-left`, bez `--collapsed` a bez media pravidla. Každé použití `--agent-navbar-w` mimo složku, které rezervuje místo vedle obsahu (například `padding-right` na `body`), se odstraní.
- `AgentNavbarRail.tsx` se přestal používat a 2026-09-17 byl smazán i se svými styly. Spolu s oběma lištami zmizela i jejich bublina `ui-kit/tooltip/`, kterou nic jiného nepoužívalo.

## Dílek 5: App (`frontend/app/components/App.tsx`)

- `const dock = usePanelDock(environment === "editor")`, volané před každým časným `return`, vedle `useLibraryNavbar`.
- Přepnutí módu (`setMode`) volá `dock.close()`.
- Řada 2 začíná `<ModeRail mode onMode editorOnly inactive={editorDocumentOpen} />` a `<PanelToggles open={dock.open} onToggle={dock.toggle} />`. Za nimi stojí `<span className="v3-grow" />` a pak dnešní skupiny. Oddělení od nástrojů řeší existující styl `.v3-tool-group`; nový vizuál jen v `panel-dock.css` a `workspace-modes.css`.
- `editor-frame`: pryč jsou `ModeRail`, `LibraryNavbar` i `agentNavbarPanel`. Za `workspace-shell` přibude `{environment === "editor" && dock.open && <PanelDropdown panel label onClose={dock.close}>…</PanelDropdown>}`. Uvnitř je `LibraryNavbar` s dnešními props bez zrušených a s `onClose={dock.close}`, nebo `AgentNavbar` s dnešními props bez `onToggle` a s `onClose={dock.close}`.
- Domovská obrazovka: `{agentNavbarPanel}` se z ní odebere.
- `.editor-frame` dostane `position: relative` v `workspace-modes.css`.

## Doladění po první implementaci (2026-09-17)

- Na 1440 px se druhá řada lišty nevešla a zalomila se. Zkratka na tlačítkách panelů (`panel-toggles__kbd`) je proto vidět až od 1700 px, pod tím ji nese jen tooltip tlačítka.
- Skupina Filtr štítků má modifikátor `v3-tool-group--shrink` (začíná na 120 px, roste do přirozené šířky, při nedostatku místa se zúží). Štítky v ní stojí v jedné řadě a posouvají se do strany.

## Co se nemění

Obsah a chování Knihovny i Agentů uvnitř panelu, tažení na plátno (`CATALOG_DRAG_TYPE`, `AGENT_DRAG_TYPE`),
zkratky Ctrl+Shift+, a Ctrl+Shift+., klíče localStorage, inspektor a jeho šířka (`--inspector-w`), horní lišta,
`project-capabilities`, backend. Zkratky Ctrl+1…5 z návrhu se nezavádějí, protože v prohlížeči přepínají
karty. Spojení obou řad lišty pod 700 px výšky okna se odkládá.

## Hotovo, když

- `npm test` a `npm run build` procházejí.
- V běžící aplikaci na 1440 × 900 v Editoru s vybranou kartou a otevřenou Knihovnou má `.canvas-area` šířku alespoň 900 px a výšku alespoň 640 px.
- Šipka panelu míří na střed tlačítka.
- Esc, klik na plátno i přepnutí módu panel zavřou.
- Položku z Knihovny i z Agentů jde přetáhnout na plátno, i když je puštěná pod panelem.
