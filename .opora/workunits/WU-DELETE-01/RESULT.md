# Odstranění položek — výsledek

Implementováno: smazání uzlu, celého sektoru s potomky, jednotlivé vazby a odpojení repozitáře z aktivního seznamu.

## Ovládání
- Vyberte uzel/sektor → tlačítko Smazat uzel / Smazat sektor v detailu.
- Klikněte na vazbu → Smazat vazbu.
- Vyberte repozitář → Odebrat repozitář v horní liště.
- Náhled uvádí skutečné počty dotčených položek; Zrušit/Escape nic nemění. Potvrdit provede jen vybranou změnu.

## Hranice
Main zůstává read-only; obsah grafu se mění v návrhu nebo pracovním prostoru. Před odstraněním vzniká recovery snapshot v lokální DB; jeho existence není důkaz provedení. Uložené NodeSpec revize zůstávají zachované. Obnovení přes UI není implementované.
Repozitář se jen odpojí z aplikace. GitHub, lokální soubory, dirty worktrees a historie se nesmažou. Aktivní Git job blokuje odpojení. Archivovaný projekt již nepovolí nový view/write/sync/workspace/job.

## Evidence
- Python: 35 testů PASS; evidence/delete-pytest.xml.
- Playwright: 14 testů PASS; evidence/delete-playwright.json.
- TypeScript/Vite build, Ruff check/format a staged diff whitespace: PASS.
- 2 dosavadní FastAPI/Starlette deprecation warnings zůstávají.
- Desktop/mobile confirmation screenshoty jsou testovací fixture, nikoli uživatelská data.
- Nezávislá kontrola REVIEW.json: PASS; všech 13 kontrolovaných source hashů beze změny. Poté přidán pouze regresní test zachování NodeSpec historie; také PASS.

## RED→GREEN
Chybějící endpoint404 → jednotlivý uzel; count1 místo4 → closure potomků; nepodporovaná vazba → samostatné odstranění hrany; chybějící odpojení → archive/guards; přímý graph write200 při úbytku ID →409 bez removal approval. Chybějící UI tlačítka → funkční potvrzení/cancel/reload.

## NEXT NODE
UI obnovení z recovery snapshotu / znovupřipojení archivu; fyzické mazání uložených kopií pouze jako samostatně schválená schopnost. Není součástí tohoto řezu.
