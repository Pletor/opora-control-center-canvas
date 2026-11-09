# Srdce → canvas: doložená diagnóza (OP-086DEE)

Audit pouze četl produkční data; níže uvedený stav byl pozorován 8. 11. 2026 nad kódem `70131036f141e6dd5d90d7842f6fd8877cf466eb`. Tento dokument nepřijímá produktová rozhodnutí ani nespouští realizaci.

## Správný projekt a podklady

Aktuální AmpleLab je GitHub projekt `5b0b4471c24a4c5bac325d38ff23921c` (`Pletor/ample`). Pracovní prostor posledního přijatého plánu je `03116e0b6f4e40dbabfc75241604ce9c`, podle `P:/opora-data/projects/5b0b4471c24a4c5bac325d38ff23921c/brain/active_workspace.json` (zapsán 3. 11. 07:12:31 UTC). Starý lokální projekt `cc5f34ec07cd455ca5ad1a69af19022b` není současný běh: má starší plán a nulové nové rešeršní karty.

Všechny dále relativní datové cesty jsou vůči `P:/opora-data/projects/5b0b4471c24a4c5bac325d38ff23921c`.

Pět požadovaných výzkumů existuje v `brain/dilna/out/research/<ID>.json`:

| Téma | ID | Fakta ve výstupu |
| --- | --- | --- |
| V1 RLS, pgvector a cache | `98aed2a33ac3425891a7d61c88a4d142` | 12 |
| V2 17 obrazovek / 7 fází | `ef0133b1f269482cb34072d6d5f8035a` | 12 |
| V3 verzování embeddingů | `8b54aa06eff949ebbdef56c3096e7db1` | 12 |
| V4 kvalita, latence a cena | `a08b6635a1a74e7b8a37a540e16ade78` | 0 |
| V5 lokátory a retrieval | `b25805ed46c943759cfac5e379750894` | 12 |

Jsou to historické výstupy z 30. 10.–1. 11., nikoli nové výzkumy z dnešního běhu. Mají `fragmentId, question, targets, digest, facts, options, stats`, ale nemají novější `scope` a `researchBatch`. Počet faktů není počet platných důkazů. Je třeba obnovit jejich původ a aktuálnost, nikoli znovu zaplatit stejný výzkum nebo všechny závěry prohlásit za ověřené.

## Chronologie a přesné místo zastavení

- `brain/batches.jsonl`, dávka `2026-10-30T08:51:13Z`, session `e2041c9a-0455-4fae-9d57-d5a719ac1364`: V2 už vedlo k doplnění tří stránek architektury. Shrnutí uvádí návrh `brain/dilna/out/ample-ui-navrh.json` a neúspěšné ostré přijetí 409, „nesoulad prázdných uzlů“. Toto je historické selhání, nikoli prokázaná aktuální chyba stejného kontraktu. Nelze tvrdit, že výzkum nikdy nevedl k plánu.
- `brain/messages.jsonl`, `2026-11-08T21:07:16Z`: Pletor předal záměr hlavního admin tenantu, požadavek rozkladu na canvasu, nejprve ověřit vlastní autentizaci a rozpory. Zpráva nese `workspace: main`.
- Dávka `21:07:17Z`, session `2c0629d8-16af-42bc-8f24-ba922545ca8d`, resumed, 26 tahů: první `ctx plan-of --project 5b0... --node 6614c688-20a5-4891-a391-8ce4c39f445d` skončí 404 `node_not_found`, protože implicitně čte `main`. Později agent správně použije explicitní pracovní prostor pro uzel Organizace. První `decide` skončí 409 „Main je pouze pro čtení“, následný explicitní `--workspace 03116...` uspěje. Přechodné chyby tedy agent sám překonal.
- Vzniká otevřený požadavek `rq_287a644d715b49389a08f8857413565f` (`intake_requirements`, workspace main, created `21:09:12Z`), název „Admin tenant: funkční prototyp (administrace, založení organizací, přihlášení jako organizace)“. Vstup `ie_0995dcde2dad4030a7a6f0f66571be2d` je označen `needs_info`.
- Událost `opora_events.id=15539`, `21:09:16.935Z`: queued `gate.ticket`, ask `gt_9bf3134954c44587b4c1387b564c371e`, session `gs_0a14939b962142b0aa2d20886ac17e4a`. Otázka rozlišuje doménu (kód admins.ample.cz, canvas admins.amplelab.cz, diktát admins.mpla.cz), vlastní scrypt/session versus Supabase Auth a impersonaci versus přihlášení vlastníka. V textu slibuje mezitím jen přesun admin modulu a založení organizace, ale dávka nevyvolá žádnou operaci plánu.
- Doplnění uživatele v `brain/messages.jsonl`, `21:07:58Z`: stavět na faktech, číst Rešerši a stávající kód; neznámé vrátit jako otázku. Další dávka `21:09:28Z`, nová session `e8f50d4b-aa8c-4599-b6d7-c8864d395977`, 15 tahů: `research-map ls` je dostupné a použité, `decide --workspace 03116...` také. Vstup `ie_53f4ee2b6d354e34bead3b8e6165a6c9` je opět `needs_info` vůči témuž požadavku.
- Událost `15540`, `21:10:03.574Z`: ask `gt_3503bee6b40749c4a8f3876c9386ae77`. Výslovně se ptá, zda přejít na Supabase Auth, nebo zůstat u vlastní autentizace, a která ze tří domén platí. Končí větou: „Karty k prototypu nevydávám, dokud to nerozhodneš.“ Oba tickety jsou při auditu stále queued, answer null.
- `brain/last_done.json`, `21:10:05Z`: „Vstup ie_53f4 veden jako needs_info k rq_287a644d; zapsáno ověřené rozhodnutí (vlastní auth, service_role, admins.ample.cz) a položena jedna otázka člověku na rozpor s canvasem a doménou; karty nevydány.“ Toto je shrnutí agenta, nikoli lidské přijetí architektury.

Kontrola `project.sqlite` v read-only režimu: 52 historických `opora_graph_proposals`, poslední `6e6dd202ca037de8b0a5fb8642f2382b024c133c` z `2026-11-03T07:12:30.548555+00:00`; dnešní návrh chybí. `research_decision_reviews=0`, `research_materializations=0`, `research_batches=2`. V obou dnešních dávkách není volání `plan` ani pokus zapsat nový návrh grafu.

**Poslední úspěšný krok:** předání záměru, čtení podkladů/kódu a zápis potřeby rozhodnutí i deníkového zjištění. **První chybějící krok:** uložení částečného návrhu plánu s lokálními blokacemi a vazbami na podklady. Nejnovější zastavení není odmítnutí canvas zápisu ani starý UI cache: žádný zápis návrhu nebyl zkusen. Rozpor domény a identity skutečně vyžaduje produktové rozhodnutí; nezdůvodňuje však blokování uložení nezávazného návrhu a nezávislých částí, které nové zadání výslovně dovoluje.

## Rozlišení scope a cesta volání

1. `backend/agi_pletor/service.py:117–120`: `heart_message` předává workspace konverzace beze změny.
2. `backend/flow/catalogs/heart/wakes.py:48–65`: `message` uloží workspace do zprávy a zařadí vstup se stejným workspace.
3. `backend/brain_opora/heart/command.py:190–197`: `child_env` nastaví `OPORA_WORKSPACE` z dávky.
4. `backend/brain_opora/heart/opora_heart.py:207`: `scope` bere env, ledaže je explicitní override.
5. `opora_heart.py:1355–1358`: implicitní active fallback platí pouze pro research, research-map, duel a vault; ne pro ctx, decide ani plan.
6. `opora_heart.py:1096–1104`: `ctx plan-of` pošle `ofWorkspace` pouze při explicitním argumentu. `backend/brain_opora/determinism/workshop.py:119–130` jinak volí `_home` cílového projektu (main u Git projektu).

Relevantní existující identity (ze souborů `brain/dilna/data/plan-of-*.json`; jejich aktuální revizi je před zápisem nutno načíst):

- `6614c688-20a5-4891-a391-8ce4c39f445d`: oblast „Tým, organizace a izolace nájemníků“.
- `c2b49d58-d204-4fe4-b6c9-8154078449df`: sektor „admins.amplelab.cz“, účel samostatná plánovaná aplikace provozovatele. Starý text „v kódu zatím není“ je kandidát na aktualizaci, ne důkaz dnešního stavu.
- `1146f356-38da-4d5c-8c0f-966a6208a2dd`: „Organizace“, rodič `f820d3f9-54a0-46c6-b815-0c81545ef103` (ampleLab), nastavení organizace a správa členů.

## Co již existuje a kde pokračování chybí

Srdce nástroje má: `command.py` kopíruje CLI a rešeršní moduly, připojuje runtime guidance. Dnešní dávka skutečně volala research-map. Nelze diagnózu zjednodušit na „Srdce nezná canvas“.

`opora_research.py:155–175` nejprve uloží úplný výstup, pak importuje rešeršní dávku, následně označí výzkum done a vrátí shrnutí/ID. Tím chrání retry po chybě importu. Nezakládá však trvalý úkol promítnutí do plánu ani neověřuje readback návrhu. Historické V1–V5 vznikly ještě před tímto formátem.

`backend/editor/research/events.py:8–16` zapisuje transakční `research.changed` do samostatné tabulky `research_events`; srdce čte `opora_events` (`wakes.py:68+`). `inputs.py:47–68` převádí ticket, failed, canvas.failed a merge.done, nikoli dokončení rešerše. Samotný durable UI event tedy není pokračováním plánování. Přímý běh LLM může pokračovat ve stejné dávce, ale chybí doložený durable závazek po jejím ukončení/restartu.

Existuje bezpečná cesta převodu přijatého výzkumného rozhodnutí (`research/decision_tasks.py`): připnuté review a provenance, idempotentní materializace, očekávaná revize a nativní návrh. Nemá se nahrazovat přímým obcházením přijetí. Stejně tak nativní `opora_agent_state.py` rozlišuje parent revision/stale návrhy a running claim platný jen s aktuální lease/token. Tyto mechanismy vlastnictví se mají znovu použít.

## První minimální funkční oprava

Vyřešit výběr pracovního plánu pro vlastní projekt z main: explicitní workspace musí vždy zvítězit; implicitní aktivní workspace lze použít pouze pro stejný projekt a existující pracovní prostor. Cizí `ctx plan-of --project OTHER` musí zachovat cílový home, explicitní `--workspace main` musí zůstat main. Výsledek musí vrátit skutečný scope, acceptedHead/digest a zdroj fallbacku, aby agent nerozmíchal revize. Prosté globální přepsání OPORA_WORKSPACE je nesprávné, protože main má legitimní architektonické operace.

Potom v reálné dávce Srdce uložit malý návrh nad existující oblastí/sektorem s konkrétními podklady a zvlášť doménovou/auth otázkou. Použít explicitní pracovní scope a `--no-accept`; nenazývat tím návrh přijatým. Po zápisu načíst autoritativní návrh, porovnat ID/revizi a ukázat jej po reloadu. Obsah návrhu nemusí čekat na finální doménu; nasazení a auth migrace na rozhodnutí čekat musí.

Další kontrakt má evidovat „výsledek výzkumu čeká na promítnutí do návrhu“ s revision/input identity, opakovatelností a označením vyřízeného přechodu až po zápisu/readbacku. Nepřidávat nekonečné buzení na každou vlastní rešeršní změnu. Změny přijatého plánu i nadále přes návrh, lidské přijetí a existující claim/epoch protokol.

## Omezení důkazu

Historický výrok agenta o doplnění architektury není sám důkaz renderu; dnešní audit nepotvrdil browserem konkrétní nový návrh, protože žádný dnešní návrh v datech není. Neukázal ani, že všechny V1–V5 zůstaly bez realizace: historické batche a merged karty naopak dokládají dílčí následné práce. Úplné mapování existujících karet na jednotlivé výzkumy je samostatný nutný krok před tvorbou dalších úkolů, aby nevznikly duplikáty.
