# UI edit safety — parent provedení a testy

## Uzavření dílčího review
Reviewer v Hermesu dokončil `deleg_e4c537f4`: passed=true, security_concerns=[], logic_errors=[], suggestions=[]. Parent přečetl přesný verdict.json a ověřil, že staged tree stále odpovídá `95f56cf5589e50939cb6a34c344893946d28ff32` a sledované source/test soubory nemají další unstaged delta. Schválení platí pro remount opravu add1→95f a související helper, nikoli pro kompletní UI nebo nasazení; není to Claude approval. Opravný řez je připraven k lokálnímu commitu, předchozí testy44UIpassed/1LIVEskipped,92backendpassed/2warnings,Ruff/build0 se vztahují k témuž kódu.

## Předchozí stav — remount oprava po review add1
Autoritativní candidate TREE je nyní `95f56cf5589e50939cb6a34c344893946d28ff32`, stále bez commitu/integrace/deploye. Předchozí add1 review našlo jeden blocker v NodeTextEditor: staré potvrzení z odpojené instance smazalo novější draft při A→B→A. Claude znovu timeoutnul; nejde o schválení.

Parent napsal `e2e/text-remount-regression.spec.ts` a ověřil RED: po reloadu se místo novějšího Y načetl starý X. Test zadržuje odpověď skutečného API zápisu a nový text zadává přes ruční editor bez autosave; tím nevzniká falešné GREEN uložením Y před kontrolou. Parent přidal unikátní token životnosti efektu a porovnání potvrzeného snapshotu před smazáním draftu. Staré odpovědi nesmějí měnit UI, plánovat další save ani vyvolávat onSaved. GREEN ověřuje přežití Y po reloadu i jeho následné explicitní uložení a další reload.

Aktuální skutečné výsledky:
- npm run build exit0 (`build-parent-remount.log`).
- Cílené testy remount + zděděné safety:4passed.
- Celá UI sada:44passed,1skipped LIVE coding (`e2e-parent-remount.log`), exit0.
- Nově znovu celý backend:92passed/2dependencywarnings; Ruff0.
- Nezávislá source-only kontrola dílčí opravy v Hermesu spuštěna `deleg_e4c537f4`, reviewer `sa-0-ccb929c8`, immutable95f protiadd1. Výstup `C:/Users/Admin/AppData/Local/hermes/handoffs/canvas-orchestration/review-text-remount-95f/verdict.json`. Toto je explicitní alternativní review po opakovaných CLI timeoutech, NE náhražka tvrzením o Claude approval. Nepollovat; callback.

Následující sekce jsou HISTORICKÝ záznam předchozího kandidáta add1; jeho tehdejší běžící review již skončilo.

## Autoritativní scope
Branch feat/natural-canvas; basef16c2ca144f0e87487b8d32d0363bd65fcafb3ab, parent staged candidate TREE add1fe77724052b8424df1cef00865cbff37ff24. Zatím NEcommitnuto, NEintegrováno, NEdeployováno. Zděděná Opus práce NodeJournal/NodeTextEditor/use-pending-edits a natural-edit-safety testy zachována. Parent sám doplnil opravy/testy níže. Read-only model selfreport není schválení.

## Nezávislé review původního base
Review-natural-f16/handoff.md skutečněpřečten: Claude timeout, žádnýverdict. Read-only scout doložil HIGH journal cross-day late-response/draftloss a MEDIUM stale links revision={0}. Parent nepřevzal hypotézy naslepo — obě chyby reprodukoval.

## Parent RED → GREEN
1. e2e/journal-scope-regression.spec.ts: skutečný API zápis A je proveden, odpověď zadržena; uživatel přepne B a píše B, uvolní se A. RED: B vAPI zůstává prázdné. Parent oprava oddělila flush closure starého scope, resetuje transientjournal stav při scopechange a zahazuje UI aktualizaci z odpovědi jiného scope. Pendingcache se při potvrzení maže pouze pokud odpovídá potvrzenému textu+revizi.
   - Při prvnímGREEN běhu navíc opraven můj testfixture expectation: backend ukládá markdown '- Pouze den B', nikoli rawinput 'Pouze den B'; prvníRED měl úplně prázdný string, takže bug byl skutečný. Assertions jsou dál přesné, žádnécontains namísto rovnosti. Nyní API A/B i reload ověřenyGREEN.
2. e2e/live-links-regression.spec.ts: RED detail i text režim po úspěšném save držícount0 místo1. Parent přidal onSaved callback NodeTextEditor a místní invalidationcounter vNodePanel/TextWorkspace. Ten refetchuje skutečné /api/node-links, nepočítá linky frontendheuristikou. Test ověřuje přidání i odstranění odkazu BEZreloadu, obarežimyGREEN.
3. Zděděné3 natural-edit-safety testy: odmítnutýsave/navigace/reload/dopozdějšíuložení textu a deníku + IME compositon prošly. Vcelésuite měl původní test kolizi generického názvu Alfa/Beta s jinýmtestem; změněna jen testdata na unikátní Bezpečný draft A/B, assertionszachovány.

## Reálné výsledky
- npm run build exit0 (zahrnuje tsc a lokálníExcalidrawfonts), build-parent-journal.log.
- npx playwright test --reporter=line exit0:43passed,1skipped(livecoding), e2e-parent-safety.log. Testserver8741 automaticky skončil, produkce8740/8738 nezměněna.
- Backend této větve parent předUIzměnami92passed/2warnings,Ruff0; během tétoopravynebyl backend měněn.

## Review gate
Nové úzké independentreview běží deleg_6b141890/sa-0-909c0038, čte JEN immutableTREEadd1 a nejvýše18kBpodklad proClaudeSonnet. Výstupy očekávány handoffs/canvas-orchestration/review-ui-safety-add1/. Nepollovat/neopakovatstará110kBreviewtime-out; callback. Doverdiktu nepovažovatdatasafety za univerzálněschválenou: zejména A→B→A, cache při selhánísessionStorage a latecallbacky stejnéhoscope vyžadují kritiku. Candidate zahrnuje8zdroj/testsouborů; evidencePNG a rootlogy nejsou staged a nesmíse přibalit hromadným gitadd.

## Zůstává mimo tentořez
Integrovaný agent/context panel, obecný codingharness a smyčka, typedchooser/mobileacceptance a Ample permissiongate. Žádné tvrzení hotovéprodukce.
