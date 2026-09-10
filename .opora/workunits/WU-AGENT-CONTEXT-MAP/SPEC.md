# WU-AGENT-CONTEXT-MAP — sdílený obraz pro člověka a agenta

## Uživatelský záměr
Z veřejné reference https://claude-brain.preview.emergentagent.com/?utm_source=share převzít užitečné principy: pochopit LLM, řídit proces sektorů/uzlů/komponent, čitelně zobrazovat vazby a připravit jednoznačné podklady pro realizující agenty. Zachovat desktopový brand a prostředí Projekt / Editor / Live Run, nezahodit předchozí editory ani rozpracované navazování zdrojů.

## Skutečně prohlédnutá reference
Veřejná stránka byla otevřena v odděleném driver-owned Chrome bez kopírování uživatelského profilu. Ověřeny obrazovky a přechody; nepoužity mutace SCAN, DISPATCH, INVOKE, ADVANCE ani COMPACT.
- `/canvas`: karty podle vrstev FE/BE/DB/Infra/Shared, hledání, filtr stavu a lifecycle. Převzít srozumitelné skupiny, nikoli nové autoritativní entity.
- `/claude`: role agentů, instruction packets a routing matrix. Převzít roli + rozsah úkolu + zdůvodnění volby, ne natvrdo uvedené modely nebo štítek ACTIVE bez aktuální telemetrie.
- `/kontext`: focus, dokumenty/piny, kontextové okno, náklady, timeline. Převzít oddělení vybraných podkladů od běhu. Zobrazené nuly a maximální kontext nepovažovat za ověřená měření.
- `/dilna`: soupis práce s vazbou na detail.
- `/dilna/claude-brain`: lifecycle osa, kritéria, kroky práce, specifikace/architektura/kód/pravidla/kontext/workflow/propojení/reporty, COPY AS MD. V záložce Propojení viděny směrované vazby a typ api_call s poznámkou.
- `/project`: projektový setup po sekcích a export Markdown. Nevytvářet vedle našich dokumentů druhý nezávislý projektový popis.
- `/bridge`: scanner, scope files_allowed, dispatch, inbox/outbox a daemon instrukce. Funkčnost transportu nezkoušena; výpočet readiness a mapování importů pouze deklaruje UI.

## První realizovaný řez — Editor / Kontext
1. Mapa reálného výběru: projekt/pracovní prostor → řetězec sektor/uzel → sourceRef (existující/navržený/legacy bez vazby).
2. Příchozí a odchozí hrany existujícího grafu. Graf nemá typ hrany: označit jako spojení v návrhu, nikoli automaticky API volání, import nebo runtime závislost.
3. Vysvětlit proces zadání → vybraný kontext → model → nástroj/akce → důkaz. Jde o výukové schéma, ne záznam myšlenek nebo runtime telemetrie.
4. Čitelný skutečný paket: cíl, ne-cíle, přejímací kritéria a zdroje z uloženého snapshotu; vynechání/zkrácení se nezatajují.
5. Markdown pro člověka/agenta z téhož snapshotu jako existující JSON. Samostatná obálka `designContext` ponese předky, focus/sourceRef a příchozí/odchozí hrany ze snímku lokálního grafu při sestavení. Není součástí identity/digestu backendového paketu. Mapa u sestaveného paketu a oba exporty musejí používat tentýž zachycený diagram, ne pozdější graf. Žádné automatické odeslání do modelu. Zachovat sestavení, validaci, JSON export, LLM návrh i Coding.

## Datové hranice a bezpečnost
- Autorita pro mapu: aktuální Graph předaný EditorWorkbench; graf může být rozpracovaný. Autorita pro snapshot: existující POST /api/context/packets a jeho ID/digest/content/sourceRefs.
- Piny/reference souborů nejsou přečtené obsahy. Formulář není paket. Bajty nejsou tokeny. Paket není celý kontext aktivního modelu.
- Změna rozsahu nebo vstupů zneplatní zobrazení předchozího paketu. Pozdní async odpověď nesmí přejít do nového scope.
- Aktuální graf nepřimíchávat do identity již sestaveného paketu. Export není potvrzení doručení agentovi a není povolení zápisu do zdrojů.
- Žádná nová backend autorita, žádné síťové volání modelů, žádná instalace nového monitoringu.
- Chybějící rodič, cyklus, prázdný výběr nebo legacy sourceRef musí mít čitelný stav, ne pád či nekonečnou smyčku.

## Další principy, zatím mimo tento řez
- Live Run: časová osa skutečných handoffů, akcí, výsledků a rozhodnutí supervizora z existujících adaptérů; absence dat = neznámé, ne nula.
- Detail uzlu: připravenost odvozovat z konkrétních kritérií, testů a artefaktů, ne procenta z LOC/TODO nebo počtu edit eventů.
- Nepřidávat druhý lifecycle vedle GitHub Project Status. Výukový postup a evidence přejímky nejsou duplicitní lifecycle autorita.
- Skutečný dispatch vyžaduje explicitní kontrolu scope, dostupného transportu a potvrzení; prohlédnutí stránky nikdy nesmí spustit agenta.

## Ověření
RED→GREEN Playwright pro skutečný Editor a snapshot, export/download, změny rozsahu/vstupů, nedoručené pozdní odpovědi, absent/legacy/cyclic graph. Build/typecheck, nezávislé review, žádné modelové POSTy. Náhled 8750 se neaktualizuje před ověřením identity a dílčího kandidáta. Širší v2 a source-creation regrese zůstávají samostatná otevřená práce.
