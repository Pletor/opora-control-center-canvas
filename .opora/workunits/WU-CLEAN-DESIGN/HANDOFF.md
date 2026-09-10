# WU-CLEAN-DESIGN — handoff (Fable 5.1, jediný writer větve design/clean-workspace)

Base `abdf852`, worktree `.worktrees/design-clean-workspace`. Lokální claude-design workflow (SKILL.md jako metodika); **hosted Claude Design nebyl přihlášen ani volán** (HTTP 403, viz CONNECTION.md), žádné tokeny, žádné extra usage. Tento výstup není výstup hosted Claude Design. Bez tvrzení nezávislého schválení.

## Co je hotové (funkční React, testováno)
Směr **COMMAND / INSPECT** (DIRECTIONS.md, volba 2). Inventura akcí a jejich nové domovy: INVENTORY.md. Slop audit před/po: SLOP-AUDIT.md (4 → 0 tells).

Shell (`src/App.tsx` + nové komponenty):
- `TopBar.tsx`: jedna lišta 48 px: projekt, segment Čistý main / Pracovní prostor + výběr worktree (jen git projekt), revize, `LOKÁLNĚ · port`, menu **Nastavení** (Nastavení plochy → dialog; Nastavení projektu → hub; Obnovit pohled; Synchronizovat main a Odebrat repozitář jen u git projektu). Menu zavírá Escape, klik mimo i volba položky.
- `ModeRail.tsx`: Struktura · Text · Kreslení · Mapa · **Běhy** (nový mód `agents`, URL `mode=agents`); bez glyfů. Levý strom vrstev odstraněn; navigace = drobeček + karty plátna.
- Obsah: hlavička jen drobeček + „Vazby mimo vrstvu“ + `+ Sektor / + Uzel`; prázdný stav tichý vlevo nahoře; stavový řádek.
- Inspektor (`<aside aria-label="Inspektor">`) řízený kontextem:
  - uzel/sektor: `NodePanel.tsx` — hlavička (Otevřít vnitřní plátno, Připravit úkol pro agenta), karty **Obsah** (bloky, zdrojový text, souvislosti) · **Zadání** (NodeSpecEditor + podstata) · **Práce** (worktree uzlu, `NodeActivity`), patička Smazat. Panely karet zůstávají připojené (`hidden`), draft podstaty přepnutím karty nezmizí; stav karty drží App, takže přežije výběr jiného uzlu. `NodeActivity` se připojuje až na kartě Práce (žádný zbytečný polling).
  - vazba: smazání s náhledem dopadu.
  - Text mód s vrstvou: `LayerContext.tsx` — Souvislosti · Deník (z obsahu přesunuto do inspektoru, `TextWorkspace` je jeden sloupec dokumentu; `textRevision` zvednut do App).
  - bez výběru: `ScopeContext.tsx` — skutečný zdroj pohledu, čas, worktree, operace, Nový pracovní prostor; v Mapě `MapTools.tsx` (počty, Propojit z/do, Export pro Archify), v Kreslení `DrawingTools` (+ wireframe paleta).
  - Běhy: `AgentsWorkspace` v obsahu, inspektor skrytý; nový prop `focusRun` pro cestu **běh → detail zdroje** z karty Práce.
- `types.ts` `api()`: ne-JSON odpověď (statický 404) hlásí `… není dostupné (HTTP 404)` místo chyby parseru — `/api/agents` v této bázi chybí a UI to říká pravdivě, nic nespouští.
- CSS: `style.css` přepsán na tokeny (`--bg/--surface/--ink/--accent/--fs-*/--sp-*`, Segoe UI Variable stack, mono jen pro identifikátory), `workspace-modes.css`, `text-workspace.css`, `project-home.css` (jen tokeny), drobné úpravy `natural-canvas.css`, `agents.css`, `drawing.css`. Breakpointy 1200 / 900 / 540; na ≤900 rail vodorovně, obsah s určitou výškou, inspektor pod obsahem, stránka roluje.
- Kopie: modal „Jedno místo. Jasný účel.“ → „Nový uzel/sektor“; odstraněn idle text „Celý systém…“ a flow-rule.

## Nezměněno (záměrně)
`NodeTextEditor`, `NodeJournal`, `use-pending-edits`, `BlockOutline`, `NodeSpecEditor`, `NodeLinksPanel`, `Board`, `ProjectMap`, `DrawingWorkspace`, `RemovalDialog`, backend, data, auth. Opravy WU-EDIT-SAFETY nedotčeny.

## Testy (TDD, skutečné běhy; logy v této složce)
- `e2e/clean-workspace.spec.ts` (nový, 7 testů): menu a lišta, git projekt, karty inspektoru + přežití draftu, Text mód s inspektorem, Běhy bez backendu (pravdivá chyba HTTP 404, žádný start), běh → detail zdroje s **FIXTURE route-mockem označeným v testu**, mobil bez přetečení + snímky.
- Upravené selektory (jen navigace, assertions zachovány): `workspace-modes`, `drawing`, `removals`, `project-home` (položky přes menu Nastavení, helper `openSettings`), `workspaces`, `node-spec` (karta Zadání, helper `openSpec`), port 8741→8742 v assertions (`drawing`, `removals`, `wireframe`, `coding`, `workspace-modes`).
- Chráněné specy beze změny a GREEN: `text-remount-regression`, `journal-scope-regression`, `natural-edit-safety`, `live-links-regression`, `natural-canvas`, `fractal-text`, `canvas`.
- `playwright.config.ts`: port 8742, `OPORA_CANVAS_DATA=.data/e2e-design-<base36>`; produkce 8740 se nedotkla, 8738/8741 nespouštěny.

Výsledky: `npm run build` exit 0 · `npx playwright test` **51 passed, 1 skipped** (LIVE coding, explicitní opt-in `OPORA_LIVE_ACCEPTANCE`), exit 0 (`e2e-full-final.log`) · `uv run pytest -q` **166 passed, 3 skipped, 2 warnings**, exit 0 · `uv run ruff check backend tests scripts` exit 0. Skip a warnings nejsou označeny jako PASS.

## Zjištěné blokery a poznámky pro rodiče
1. **Délka cesty Gitu na Windows**: `prepare_e2e` selhával na `git worktree add` (`fatal: '$GIT_DIR' too big`) u `removal-fixture`, když má datový kořen ≥ 147 znaků. Kratší unikát v `playwright.config.ts` to řeší; hranice změřena bisekcí. Netýká se backendu.
2. `/api/agents` v této bázi neexistuje; UI Běhy/Práce ukazují HTTP 404. Po převzetí backend commitu rodičem test „běhy bez backendu“ automaticky přejde na větev „API dostupné“ (test sondou zjišťuje stav). Fixture-mock test je jen kontrakt UI, ne důkaz integrace.
3. Existující specy během běhu přepisují sledované `evidence/*.png`; tyto soubory jsem po běhu vrátil (`git checkout -- evidence/<sledované>`) a necommituji. Vlastní snímky: `evidence/design-desktop.png`, `design-text.png`, `design-mobile.png`, `design-before-*.png` (z HEAD).
4. Mimo řez: re-kompozice ProjectHome (jen tokeny), zavřený `<details>` zdrojového textu (drží ho přímá editace + stávající testy), plovoucí inspektor / Ctrl+K paleta (směr 3), druhá vizuální iterace přes hosted Claude Design po `/design-login`.

## Commit
Jen vlastní soubory (src/**, e2e/**, playwright.config.ts, tato složka, evidence/design-*). SHA je v EVIDENCE.json.
