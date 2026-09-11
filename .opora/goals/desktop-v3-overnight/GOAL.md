# GOAL — OPORA Desktop v3, poté bod 2 podle fotografií

## Autorita a pořadí
Uživatel Helmar, Telegram, 2026-09-11: pracovat autonomně celou noc, používat Claude Code (Opus/Sonnet), po resetu využít dostupnou kapacitu na skutečnou implementaci. Nejdříve bod 1: implementovaný Desktop v3, každá komponenta funkční. Až po ověření bodu 1 pokračovat bodem 2 podle dříve zaslaných fotografií. Výsledek = fungující otestovaná aplikace, ne samotný plán nebo maketa.
Poslední konkrétní oprava: inspektor bez aktivního Wireframe má rozbitý layout a nesmí rozbíjet menu.

## Zdroje
- Jediná integrační větev: `integration/desktop-v3`, worktree `C:/Users/Admin/opora-v3`.
- Skutečná předloha (číst celou, žádná náhradní fantazie): `C:/Users/Admin/AppData/Local/hermes/handoffs/canvas-orchestration/desktop-v3/06 OPORA Desktop v3.dc.html`.
- API/UX kontrakt: stejný adresář, `CONTRACT.md`.
- Předloha online (uživatel povolil browser): `https://claude.ai/design/p/66ce0bf9-4cb8-4f05-9c00-44f392093bf7?file=06+OPORA+Desktop+v3.dc.html`.
- Evidence, prompty, registry CLI lanes: `C:/Users/Admin/AppData/Local/hermes/handoffs/canvas-orchestration/desktop-v3` (dále E).
- Wrapper pro skutečný Claude Code: `C:/Users/Admin/AppData/Local/hermes/handoffs/canvas-orchestration/run_claude_lane.py`, JSON spec podle `E/inspector-style-spec.json`. Windows Job omezuje celý strom. Max turns a deadline jsou skutečné limity, nikoli důkaz quota.
- Read-only inspirace/původní dirty práce: `P:/0. OSVC/8. Code/07. Aplikace/02.Opora-control-center/Opora-control-center-canvas/.worktrees/v2-document-task`. Nesmí se přepsat ani vyčistit.
- NOVÉ PŘÍMÉ ZADÁNÍ UŽIVATELE + BOD 2: všech 11 fotografií nyní DODÁNO a ověřeně archivováno. Před další prací POVINNĚ načíst `C:/Users/Admin/AppData/Local/hermes/handoffs/canvas-orchestration/desktop-v3/phase2-user-references/USER-BRIEF.md` a sousední `manifest.json`. Toto nahrazuje staré missing_source v STATE/checkpointu. Bod1 = funkční Desktop v3 a doložený průchod technická dokumentace → schválený snapshot → skutečný agent → artefakt a ověření zpět v UI; samotný export/proposal nestačí. Bod2 až po akceptaci bodu1: zachovat layout v3 a pouze ho rozšířit/vyšperkovat podle těchto fotografií. Nebudovat náhradní layout. Koordinátor převezme nové zdroje do STATE a commitne doplnění GOAL; rodič implementační cesty nemění.

## Akceptace bodu 1 — každý bod potřebuje konkrétní důkaz
- [ ] Inventář VŠECH komponent a interakcí originální předlohy, porovnání implemented/tested/missing. Nejen ručně vybraná podmnožina.
- [ ] Canvas-first desktop shell, OPORA brand, světlo/tma, hustota; 1280/1440/1920px bez přetečení a kolizí.
- [ ] Projekt: zdrojový strom, skutečné reference, podstata/dokumentace, nastavení, zachovaný projekt/workspace kontext.
- [ ] Editor: struktura, mapa, text, kreslení, wireframe, dokumentace, nástroje, ukládání, konflikty, reload a přepínání bez ztráty dat.
- [ ] Inspektor: především native Excalidraw selected-shape inspector bez Wireframe; barvy/posuvníky/popovers a menu bez kolize s OPORA CSS. Také OPORA pravý panel bez překrývání a dostupné akce.
- [ ] Paměť projektu, rozhodnutí, pravidla, životní cyklus uzlu a task kroky skutečně persistují, scope/readonly/revize fungují.
- [ ] Podklady: dokumenty, mapa, zadání, pravidla, zdroje, relevantní kresby předků i uzlu, skutečný scope session; manifest zahrnutí/vynechání/neuložených zdrojů; SHA snapshot je neměnný a přesně tentýž jde agentovi.
- [ ] Live Run: layout v3, skutečné sessions/výstupy, hledání/filtry, 7 karet, tickety, časová osa, doložené náklady a ověřené ovládání. Nepřebírat ilustrační data předlohy.
- [ ] Retained advanced viewer (Dohled běhů): stránkování, source health, náklady/paměť/telemetrie, vazby k uzlům a deep-links stále fungují.
- [ ] Každé tlačítko/interakce návrhu má skutečný end-to-end účinek, nebo explicitně evidovaný externí blocker. Disabled placeholder NEZNAMENÁ dokončená komponenta. Chybějící transport /btw/fork/resume/obecné coding prověřit proti skutečnému runtime a bezpečně implementovat, pokud je v rozsahu a existuje podporovaný kontrakt. Neobcházet přihlášení/oprávnění; nevymýšlet API ani billing hodnoty.
- [ ] RED→GREEN pro opravy, nezávislé Claude Code review, kompletní pytest/Ruff/TypeScript/build/Playwright a skutečný browser smoke po publikaci. Skips a nereprodukovaná či externě blokovaná kritéria uvést pravdivě.
- [ ] Ověřená práce sloučená v integration/desktop-v3, žádný aktivní writer na témže worktree, commit + append-only checkpoint + funkční náhled.

## Pracovní smyčka
1. Přečíst GOAL, STATE.json, poslední CHECKPOINT a registry `E/*/state.json`; ověřit procesy a git. Nikdy nevstupovat jako writer do aktivní Claude lane.
2. NOVĚ uživatel výslovně povolil až ČTYŘI současné Claude CLI lanes. Před dispatch číst `E/four-claude-authorization.md` s přesnými novými rezervacemi export-scope-hardening a workflow-draft-preservation; nespouštět jejich duplicity. Tento novější limit nahrazuje staré2+1 v cron promptu. Jeden úzký ověřitelný krok na agenta, výlučné cesty a samostatný worktree; max4 celkem včetně reviewerů a test lanes. Opus pro složité hranice, Sonnet pro UI/testy. Jen noční koordinátor integruje; po skutečném quota resetu pokračovat, nikoli restartovat počítač.
3. Claude CLI spouštět skutečně přes bounded wrapper. Na začátku readiness/auth bez odhalení tajemství. OAuth/Max ponechat; žádný nevyžádaný přechod na placený API provider. `subtype=success` nestačí: potřebný commit, dokončené testy a readback.
4. Po každém kroku důkaz, review, sloučení a aktualizovaný náhled. Při konfliktu číst a zachovat obě práce, ne reset/rebase/smazání.
5. Dlouhý CLI/test spustit jako trvalý background proces a uložit jeho spec/handle do STATE, aby další cron iterace pokračovala. Cron iterace má omezený čas — nečekat v ní na celý noční vývoj. Nezanechat neoznačený writer; další iterace nejdříve zpracuje existující výsledky.
6. Kvótu respektovat: uživatel hlásil 75% použito, reset za53min od cca01:50 CEST (odhad02:43 CEST; není nezávisle změřeno). Při skutečném quota error uložit observed reset/retry čas, žádná horká retry smyčka. Po resetu obnovit smysluplné paralelní implementace/testy. Nevyrábět práci jen kvůli spotřebě tokenů.
7. Po skutečném splnění bodu1 přejít na doložené zadání/fotografie bodu2. Při chybějících zdrojích uchovat blocker a čekat na doplnění, ne falšovat hotový výsledek.

## Bezpečnost a preview
- Žádný automatický model start při pouhém otevření/přepnutí/přípravě kontextu. Konceptuální uzel nedává filesystem práva.
- Žádné osobní údaje/tajemství v logu, commitech, reportech. Žádné heslo/token do browseru. Runtime dry-run/readiness ≠ placený model spuštěn.
- Vlastní náhled: `http://127.0.0.1:8780/`, kopie dat (`C:/Users/Admin/opora-v3/.data/desktop-v3-preview-data`). Původní porty8768 a8740 a cizí procesy NEMĚNIT.
- Frontend: `node node_modules/vite/bin/vite.js build --outDir .data/v3-live-dist --emptyOutDir`, pak `python E/publish_live_preview.py` (nahradit E skutečnou cestou).
- Backend restart pouze po ověření vlastního PID/cmdline a záloze přes `E/stop_owned_preview.py`, pak `uv run python E/serve_preview.py` jako background server. Poté HTTP+browser readback. Zachovat změny uživatele v preview kopii, neobnovovat starou DB.
- Reálné ověření: `node E/verify-unified-context.cjs` a `node E/verify-live-redesign.cjs` (první vytváří jasně označený prepared QA úkol pouze v kopii dat, žádný model).
- Test porty8742/8769/8771 sdílejí všechny clean-editor konfigurace: jen jeden test runner. V3 panel harness8782 samostatně.
- Frontend/UI změny prezentovat průběžně v náhledu. Telegram pouze text, žádné audio. Heartbeat stručně při skutečném posunu/blockeru, ne opakované prázdné statusy.

## Stop pravidlo
DONE pouze když obě fáze mají doložené akceptace a nejsou nevyřešené funkční komponenty. Uživatelův stop/nové zadání má přednost. Když další krok vyžaduje nedostupné přihlášení, chybějící fotografie nebo neudělené oprávnění, označit BLOCKED a spotřebu na stejném blockeru nezvyšovat. Trvalý monitor bude při nezměněném stavu tichý.
