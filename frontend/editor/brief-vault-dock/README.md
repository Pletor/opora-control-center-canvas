Schránka zadání v levém menu Editoru: sekce `vault` („Schránka“, zkratka Ctrl+Shift+.) menu `frontend/layout/panel-dock/` v širokém panelu vedle lišty, ne modální okno. Kontrakt: `docs/navrh-schranka-zadani.md`, sekce „Dvě stopy a levé menu“ (a starší „Schránka jako pop-up s levým menu“ pro obsah sekcí). Kód ho provádí, nemění.

**Proč tady.** Schránka už nepatří detailu karty (záložka zmizela), je to samostatné místo Editoru vedle Struktury, proto je to vlastní feature složka `frontend/editor/brief-vault-dock/` (dřív `node-detail/brief-vault-window/`, modální obal smazán). Sdílený model stromu, jeden zdroj dat (`brief-vault-store`), strom s detailem fragmentu a čipy karty zůstávají v `frontend/editor/node-detail/brief-vault/`, protože je čte i karta a Board (čipy „Ze schránky“, odznak „zadání se změnilo“).

**Kdo ji otevírá.** Položka Schránka v liště menu, čipy „Ze schránky“ v Zadání karty, čip fragmentu u Podnětu a tlačítko „Otevřít ve Schránce“ u sektoru či karty s vlastní schránkou. Všechno jde přes `openVault(scope, focus?)` v App: otevře sekci menu (`dock.open("vault")`), přepne rozsah na vlastníka kořene, otevře fragment v sekci Zadání a přepne stopu na jeho `effectiveTrack`. Bez požadavku je rozsahem otevřená vrstva nebo plátno (`layer?.id ?? ""`); požadavek platí do změny vrstvy či prostoru.

**Dílky** (`components/`)

- `BriefVaultDock.tsx` — rodič Schránky: přepínač stop nahoře, vnitřní menu a jedna sekce. Strom bere ze sdíleného zdroje (`useBriefVault`), zúží ho na rozsah (`rootsOf`) a na stopu (`filterByTrack`); sekce dostávají jen zúžený strom. Rozsah, fokus a obnovu plátna po vložení karet drží App (`onPlanApplied`, `onStateChanged`). Props `{ project, workspace, scope, owner, focus, state, nodes, digest, readOnly, onOpenNode, onPlanApplied, onStateChanged }`.
- `TrackSwitch.tsx` — CX/UX/UI · Backend + DB · Nezařazené s počtem kapitol (`data-testid="vault-track-<ux|logic|none>"`).
- `VaultNav.tsx` — vnitřní menu (hledání, Plán · Vývoj · Know-how · Historie s počty, vlastník dole).
- `RootCreateForm.tsx` — „Nové zadání“: kořen vždy se stopou (`op: "create"`, `scopeNodeId`, `track`).
- `TrackReassign.tsx` — v detailu fragmentu „Stopa: … · vlastní/zděděná“ a přeřazení (`op: "set-track"`, `expectedRevision` = poslední revize ze stromu; „dědit po předkovi“ = `track: null`).
- Sekce: `OverviewSection`, `MvpSection` + `PlanPreview` (dryRun náhled, zápis po potvrzení), `ResearchSection` + `ResearchDetail` + `FeedbackBox` + `PromoteForm`, `QuestionsSection`, `FeedbackSection`, `KnowHowSections` (Rozhodnutí, Podklady, Podněty), `HistorySection`, `FragmentActions` (Zadat výzkum, Položit otázku). Sekce Zadání znovu používá `node-detail/brief-vault/components/BriefVaultPanel` (předek jiné stopy je ztlumený jako cesta).

**Logika** (`logic/`, testy vedle)

- `vault-tracks.ts` — stopy a popisky, platná stopa (`viewOf`, se zpětnou kompatibilitou dědění bez `effectiveTrack`), `filterByTrack` (cesta ke kořeni zůstane s `offTrack: true`, nepočítá se do pokrytí ani MVP a nestane se kartou), `trackCounts`, `pickTrack` (zapamatovaná volba, jinak první stopa s obsahem). Volba se ukládá jednou pro aplikaci pod `opora:vault-track:v1` (nikdy per projekt); `use-vault-track.ts` je jen vazba na React.
- `vault-drafts.ts` — rozepsaný text: `isDraftField` (textové pole, ne hledání a přepínače), `hasUnsavedDraft`, `pruneDrafts`, `keepVaultMounted(open, dirty)`. `BriefVaultDock` si pamatuje pole, do kterých člověk psal, a hlásí `onDirty`; dokud je text neodeslaný, App drží Schránku namountovanou a jen skrytou (`kept` v `PanelDock`), i když člověk přepne sekci nebo zavře menu, a nemění jí rozsah. Po odeslání se pole vyprázdní; kontrola běží přes sdílený poller (`createPoller`, jen místní, bez sítě).
- `vault-tracks.ts` → též `ideaTarget`: fragment z Podnětu jde pod kořen vybrané stopy, jinak do nového kořene se stopou (`from-idea` se `scopeNodeId` + `track`); ve stopě Nezařazené zvolí stopu člověk výběrem v sekci Podněty.
- `vault-dock-model.ts` — sekce menu, počty, hledání bez diakritiky (`filterTree`), výzkum s verdiktem, otázky, „Čeká na tebe“, bezpečné odkazy (`safeHref`), rozsah (`scopeIds`) a vlastník schránky (`ownerLabel`).
- `vault-plan.ts` — koncept `/api/canvas-plan` z fragmentů („Vložit vybrané jako karty“, „Rozdistribuovat zbytek plánu“; `fragmentRef`, podfragmenty = bloky, strop 200 karet). Vrstva podle stopy: CX/UX/UI → `card.layer = "frontend"`, Backend + DB → `"backend"` a po nejvýš 36 blocích z podfragmentů vždy čtyři závěrečné bloky `LOGIC_BLOCKS` (Funkce a metody · Spolupráce · Test částí · Komponenta s portem `Komponenta hotová → frontend`), nezařazené → bez vrstvy.
- `vault-actions.ts` — zápis `POST /api/brief-vault` (op) s obnovou sdíleného stromu, čtení historie a balíčku `research-brief`.

**Styl**

`styles/brief-vault-dock.css`: blok `vault-dock` (panel, přepínač stop, vnitřní menu, hlavička) a bloky sekcí `vault-panel`, `vault-tile`, `vault-button`, `vault-mvp`, `vault-row` …, každý s příběhovým komentářem. Šířku panelu dává `panel-drawer--wide` v `layout/panel-dock`.

**Co zmizelo s modálem.** `<dialog>`, × a Esc okna (panel zavírá lišta, ☰ a Esc menu), dotaz `window.confirm` na rozepsaný text při zavření (nahrazený držením skryté Schránky, viz `vault-drafts.ts`), `BriefVaultEntry` (vstup v záložce Schránka) a `BriefVaultScope` (inspektor plátna/vrstvy).
