# Parent recovery after agents-sonnet-finish max-turns

## Aktuální převzetí — reviewed backend candidate 17a
Předchozí části níže jsou historický stav. Po dalším ukončeném Sonnet běhu parent převzal změny a opravil validaci nestringových sourceId/authorType (RED→GREEN), dále přečetl skutečný výsledek finálního Claude review. Wrapper proc_df4542f0f26f exit1 znamenal zamítnutý verdict, NE timeout: ClaudeCLI exit0/subtype success, security_concerns obsahovaly jediný blocker v redakci tokenových klíčů. Přesný reviewed tree:22551f6a49ac983b9d25c5aa77d18a29c763ab40; envelope v Hermes handoffs/canvas-orchestration/review-observability-close-round2/.

Parent přidal tests/test_agent_token_redaction.py. RED:13failed/8passed — camelCase/prefix/plural a string pod názvem metriky unikaly. Oprava maskuje všechny tokenové klíče, s výjimkou explicitně známých číselných metrik. Rekurzivní redakce nemění vstup; bool není číslo pro tuto výjimku. Současně zůstávají čitelné skutečné input/output/cache/total token counts.

Skutečný fullpytest po opravě:162passed,3skipped symlink,2dependencywarnings; Ruff0. Nový immutable candidate TREE17a988d8369254ee8ab00727d9ccbdce9343b234 získal nezávislý Claude Sonnet PASS pro opravný delta diff (security_concerns=[],logic_errors=[]). Envelope: C:/Users/Admin/AppData/Local/hermes/handoffs/canvas-orchestration/review-token-redaction-17a/verdict-envelope.json. CLI exit0, wrapper exit0, žádný timeout. Kontrola call sites potvrdila pouze definici _secret_key a volání s (key,item).

Backend opravy jsou připravené k lokálnímu commitu, NE k prohlášení hotového produktu. App.py/App.tsx integrace, frontendové trust zobrazení a live Bridge ověření zůstávají otevřené; žádné změny produkce8740/8738. Tři symlink testy zůstávají skipped. Neblokující review suggestions: omezit délku rawsummary před regexredakcí a zdokumentovat nutnost reentrant canvas.lock. Nezávislý source-event resolver stále chybí; klientské claims zůstávají unverified.

## Historický záznam před finálními opravami

## Stav
Worker session ac9efd21-574d-4dcb-8fb6-0ca3697c7132 skončil exit1,error_max_turns (45 kroků), localTreeInactive:true. Nebyl to doložený quota limit. Změny zachovány na feat/agent-observability, HEAD302f59a, zatím UNCOMMITTED/UNREVIEWED. Parent nespustil náhradního writera. Produkce8740/8738 nedotčena, moduly dosud nejsou připojené do app.py/App.tsx.

## Parent ověření a opravy
- První nezávislý běh agent boundary/activity/bindings/sources:3failed,42passed,3skipped,2warnings. Všechny tři HTTP failure měly405, nikoli doménovou odpověď.
- Příčina: test fixture přidával agent router až za catch-all StaticFiles mount('/'). Opraveno JEN pořadí route registrace fixture; všechny mounts jsou zachované, origin middleware rovněž, žádná response assertion oslabena. Při skutečné integraci MUSÍ být app.include_router(create_agent_router(service)) PŘED app.mount('/'). Toto není hotová produkční integrace.
- Nový parent test test_client_cannot_confirm_fabricated_source_event nejprve RED: vymyšlená událost od klienta získala source_confirmed jen díky autorType=source_event a existující vazbě. Vazba neověřuje event ani obsah.
- Minimální GREEN: source_event nyní získá unverified_source_claim, operator_note zůstává unverified_note. Opraven komentář politiky a původní dedup test, jehož fixture neobsahuje žádný zdrojový důkaz. Nejde o implementaci ověřeného source-event resolveru; ten zůstává chybějící.
- Parent full `uv run pytest -q`: exit0,134passed,3skipped,2dependency deprecation warnings.
- Parent full `uv run ruff check backend tests scripts`: exit0,All checks passed.

## Zbývající brány
- Nezávislé Claude review celého opravného diffu ještě nebylo provedeno. Žádný závěr security-approved ani commit/deploy.
- Tři symlink escape testy byly Windows prostředím SKIPPED. Neoznačovat za prošlé; doplnit reálný proveditelný Windows junction/symlink holdout podle dostupných oprávnění, bez zvyšování oprávnění.
- Worker opět pipeoval testy přes tail; jeho exit claims nejsou evidence. Výše jsou skutečné parent nepřepipované výsledky.
- Část worker testů byla napsána až po změně kódu. RED provenance nelze zpětně předstírat. Parent potvrzuje vlastní RED pro sourceTrust a původní reprodukce 501-event/missing-source.
- Čtení starších již uložených source_confirmed hodnot není novou politikou migrováno; před jakýmkoli nasazením ověřit output-boundary kompatibilitu se starými záznamy. Tato lane dosud produkční databázi nepoužívala.
- Live observation zatím bez nezávislého holdoutu větších/rotovaných/souběžně rostoucích logů a naplněného 8738 API. Bridge dříve unavailable; nevymýšlet živost.
- AMPLE permission brána z hlavního CHECKPOINT zůstává nedotčená.
