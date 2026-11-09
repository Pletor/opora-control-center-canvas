# Trvalé plánování po výzkumu

OP-B171BE. Rozšíření zachovává původní fragmenty, výstupy rešerší, zpětnou vazbu i revize. Neprovádí přijetí návrhu ani produktovou realizaci.

## Import a obnova

`POST /api/research` přijímá vedle původních `project`, `workspace`, `key`, `operations` volitelný `continuation: {researchId, sourceFragmentId, sourceRevision}`. Výzkumný příkaz jej přidává teprve po dokončení výzkumného stolu do uloženého souboru `researchBatch`. Import mapy, receipt a událost `research.planning.requested` vznikají v jedné transakci. Pád po importu před aktualizací původního fragmentu neztratí plánovací návaznost. Obecné změny mapy bez tohoto pole nic neplánují. Replay kontroluje i původní intent.

Receipt má jedinečnou identitu projektu, prostoru, karty a revize výzkumu. Nese původní fragment/revizi, stabilní `operationId`, počet pokusů, poslední nativní `flowRunId`, stav, chybu a doložené `proposalId`. `GET /api/research/continuations?project=P&workspace=W` jej čte přes stejnou autorizační hranici jako výzkum.

Stávající Heart polling zjišťuje návaznosti při každém průchodu, také před prvním outbox kurzorem. Existující `flow_runs.trigger.payload.items` je záznam skutečně spuštěných pokusů; pád mezi založením běhu a aktualizací receipt nezpůsobí druhý běh. Srdce používá vlastní frontu, limity, tokeny a scheduler. Další worker nevzniká. Identické čekající vstupy se v paměti nesčítají.

Stavy návaznosti: `pending`, `running`, `complete`, `conflict`, `exhausted`, `blocked_context`. Konec LLM procesu bez ověřeného návrhu není úspěch. Po skončeném pokusu následuje odklad 60 sekund × počet pokusů; nejvýše tři skutečné běhy. Konflikt zdrojové revize nebo neúplná operace vyžaduje smíření; nová identita se nevytváří. Návrh nebudí další obecný výzkum.

**První návrh:** bez přijaté hlavy používá stejná operace nativní `canvas-plan` s přesným `researchSource`. Server při zápisu ověřuje `acceptedHeadAtWrite: null`; receipt uchovává digest grafu, revizi a digest stavu, skutečná ID uzlů a hran a revize/digesty dokumentů. Potvrzení znovu ověří tyto autoritativní hodnoty. Výsledek má `resultKind: canvasDraft`, `proposalId: null` a `canvasDraft` s důkazy. Existující přijatý kontext používá `resultKind: proposal` a skutečné `proposalId`. Žádná cesta automaticky nepřijímá základní graf; dřívější `blocked_context` se obnoví pod původní identitou.

## Důkaz výsledku

Nové dokončení skutečného příkazu `research` přidává do `continuation` také `finalization: {status:"done",verdict,confidence,approach,evidence}`. Jde o přesný zamýšlený výstup nativního `research-update`, uložený do stejného opakovatelného artefaktu jako mapa. Import vytvoří `awaiting_finalization`; pozorování nativní historie přepne na `pending` až po nalezení přesného dokončeného výstupu. Bez tohoto dokladu nelze vytvořit či přijmout navazující návrh. Původní importy bez tohoto pole zůstávají kompatibilní s výslovně omezeným pokrytím. Podrobnosti a kontroly změn jsou v [kontraktu předání](2026-11-08-research-execution-evidence.md).

Plán nese `draftVersion: 3` a `researchSource: {continuationId,researchId,researchRevision,sourceFragmentId,sourceRevision}`. Nativní vytvoření návrhu ověřuje tyto piny proti scoped receipt a aktuální revizi výzkumu. Zpětné čtení uchovává historické piny. Nejde o schválení pravdivosti tvrzení.

Potvrzení návaznosti vyžaduje dokončený nativní graph-proposal operation receipt autora `agent/heart`, přesný projekt/prostor/operationId, odpovídající piny a zpětné načtení celého neměnného návrhu. Kontroluje se efektivní změna grafu, dokumentů nebo stavu. Stejné ID operace s jiným výzkumem nestačí. Lidské přijetí mezi zápisem a pollingem není chyba: `acceptedAtReadback` zaznamená skutečnost, potvrzovací cesta sama nepřijímá. Stav návaznosti není stav běhu původní rešerše, platnost zjištění, schválení rozhodnutí ani dokončení práce.

## Původní výzkum

`GET /api/research/originals/ID?project=P&workspace=W&revision=N` vrací `origin: brief-vault`, `type: original-research`, `sourceRevision`, samostatnou `detailsRevision`, původní fragment, historii, detaily a feedback. Existující soubor `brain/dilna/out/research/ID.json` se vrací samostatně s SHA256; starý soubor bez uloženého scope je tak označen a nemusí odpovídat aktuálnímu kolu. Cizí explicitní scope se nezpřístupní. `research-map show ID` po 404 mapové karty zkusí tuto cestu; původní fragment nepředstírá jako mapovou kartu.

`POST /api/research/originals/ID/materialize` s `{project,workspace,revision,detailsRevision}` vytvoří nebo aktualizuje jednu stabilní mapovou otázku původního fragmentu. Klíč požadavku obsahuje obě zdrojové revize, ID karty pouze scope a původní ID. Starší revize nesmí přepsat aktuální zdroj. Při novém kole zůstávají ruční reference, vztahy, téma a stav otázky; zdrojové tvrzení se označí jako znovu neověřené. Karta nese kompaktní piny a odkaz na úplný originál, nekopíruje do každé revize všechny předchozí historie. Materializace nezakládá plánovací návaznost ani nemění `assigned` na `done`.

## Kompatibilita

Nová tabulka je pouze přidaná. Původní importy bez intentu mají stejné replay digesty. Stará data se nepřepisují ani nemažou. Návrat staršího kódu ponechá nové receipts neobsloužené, ale zachová původní výzkum i nativní návrhy; návrat nového kódu je znovu dohledá. Žádná destruktivní fáze migrace se neprovádí.
