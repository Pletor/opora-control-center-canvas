# WU-DOCUMENT-TASK — první skutečný izolovaný úkol

## Cíl a UX
Po sestavení paketu člověk zadá dokumentační úkol. Připravit zadání uloží neměnný náhled (bez modelu); samostatné potvrzení spustí přímo Hermes. Agent má pouze scope-bound nástroje na čtení schváleného kontextu a vytvoření result.md v novém serverem vytvořeném izolovaném Git prostoru. UI ukazuje skutečný běh, události, stop a ověřený dokument. Výstup lze stáhnout. Nic se neaplikuje do uživatelova zdrojového repozitáře. Toto je explicitně dokumentační typ úkolu, nikoli obecné programování nebo hotový orchestrátor.

## Architektura
Samostatný nový Canvas podle README/PRODUCT-CONTRACT. Žádná závislost na starém OporaCC/Bridge. Znovu použít bezpečnostní vzor backend/coding_worker.py: přímý instalovaný Hermes AIAgent, přesný vlastní katalog nástrojů, žádný host shell/file/web/delegation nástroj. Neměnit původní calculator runner ani globální Hermes config/profily.

## HTTP kontrakt pro UI
- GET /api/task-handoffs/capabilities?project=... → {available:boolean, reason:string|null, mode:'isolated_documentation', provider:string|null,model:string|null,budgetSeconds:number|null}.
- POST /api/task-handoffs/prepare {packetId:string,task:string} → immutable preview {id,digest,scope:{project,workspace,node},task,allowedFiles:['result.md'],readableNodeIds:string[],contextSummary,provider,model,budgetSeconds,status:'prepared'}. Server čerpá existující uložený paket, skutečnou mapu a související uloženou dokumentaci; nepřijímá klientské cesty/credentials.
- POST /api/task-handoffs/{id}/start {digest:string,confirmed:true} → run snapshot. Stejný identický start nesmí vytvořit druhý proces; jiný digest/false fail-closed. Před prvním startem ověřit aktuálnost paketu,mapy,dokumentace i settings.
- GET /api/task-handoffs/{id} → snapshot {id,status,scope,events:[{kind,...}],verification:{passed:boolean|null,...},result:{content:string,sha256:string}|null,error:string|null}. Stavy prepared,starting,running,completed,failed,cancelled,interrupted; completed pouze po skutečné nezávislé kontrole souboru. Nedělat paralelní lifecycle WorkUnitů.
- GET /api/task-handoffs/{id}/export → přesný neměnný redigovaný task/context snapshot viditelný worker custom nástroji; bez interních cest, credentials a neexportovaných serverových polí.
- POST /api/task-handoffs/{id}/stop {confirmed:true} → snapshot až po ověření zastavení vlastního procesu/stromu. Nic nerestartuje.
- GET /api/task-handoffs?project=...&workspace=... → {runs:[snapshot summaries]} pro návrat po reloadu/scope změně.

## Bezpečnost
Main se nespouští. Jen potvrzený start. Povolen jediný serverem zvolený výstup result.md, žádné čtení credentials ani arbitrary filesystem/network/commands. Symlink/junction/path traversal fail-closed. On-demand kontext je neměnný schválený výřez mapy + podkladů; UI uvede jeho hranice, není automatický přístup na disk. Mapu/spec/text/dokumentaci je nutno redigovat a velikostně omezit. Reference není důkaz přečteného obsahu. Celý katalog toolů ověřit před prvním voláním; konečný lokální deadline, max iterace a stop pro celý vlastní child tree. Při restartu není auto-resume. Žádné předstírané metriky/ceny.

## Důkaz
TDD pro server, UI a stale/duplicate/stop/refusal hranice; mocks jen explicitní testovací doubles. Nakonec jeden skutečný nízkorozpočtový Hermes běh v izolovaných testovacích datech: dočtení kontextu nástrojem, skutečný zápis result.md, kontrola obsah/hash/Git prostoru a žádné změny uživatelova projektu. Selhání poskytovatele není úspěch a nesmí se nahradit syntetickým výsledkem.
