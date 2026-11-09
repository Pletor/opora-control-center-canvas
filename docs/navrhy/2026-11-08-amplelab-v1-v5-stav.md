# AmpleLab V1–V5: aktuální podklady plánu

OP-086DEE. Audit 8. 11. 2026 je čtení skutečných dat a kódu, nikoliv nové produktové schválení. Neproběhla změna AmpleLab, spuštění migrací, agentní realizace ani měření produkční databáze. Technologické podklady jsou odděleně v `2026-11-08-amplelab-primarni-zdroje.md`.

## Identita a původ

Autoritativní projekt je `5b0b4471c24a4c5bac325d38ff23921c`, prostor `03116e0b6f4e40dbabfc75241604ce9c`. Zdrojový repozitář `https://github.com/Pletor/ample`; pracovní kopie `P:/opora-data/projects/5b0b4471c24a4c5bac325d38ff23921c/worktrees/03116e0b`. Její čistý HEAD i projektový `main` jsou `c2dc67a71df5824b7916686e15886c57b6e42787`. Všechny níže uvedené cesty produktu jsou relativní k této kopii a revizi.

Jiný registrovaný projekt `cc5f34ec07cd455ca5ad1a69af19022b`, také nazvaný ample, odkazuje na `I:/1. Projekty/01_ITNeskola/06_AmpleLab/ample` s HEAD `8e7cced51594d28909ea2b51292cc890d1b44bd1`. Není zdrojem těchto pěti výzkumů. Shoda názvu není shoda dat.

Původní výzkumy jsou ve SQLite projektu: `brief_fragment_revisions`, `brief_fragment_details`, `brief_fragment_feedback`. Úplný výstup stolu je v `brain/dilna/out/research/{fragmentId}.json`, cíle a dostupnost zdrojů v `brain/dilna/data/research/{fragmentId}/index.json`. Čteno přes SQLite `mode=ro`; všechny původní revize, fields a feedback zůstaly beze změny. Jejich přesná kopie pro audit je `C:/Users/Admin/AppData/Local/Temp/opora-plan-proof/ample-research-originals.json`.

| Téma | Stabilní fragment ID | Přesný název | Revize / běh | Platnost závěru | Důkazy v detailu |
|---|---|---|---|---|---|
| V1 | `98aed2a33ac3425891a7d61c88a4d142` | F1 Ample: RLS, vektor a verze cache | 3 / assigned, kolo 2 | feasible / medium z předchozího kola | 2 |
| V2 | `ef0133b1f269482cb34072d6d5f8035a` | Návrh Ample vs. kód: mezery obrazovek a sekcí | 2 / done, kolo 1 | unverified / medium | 0 |
| V3 | `8b54aa06eff949ebbdef56c3096e7db1` | Schéma verzovaných vektorů pro změnu embeddingu | 2 / done, kolo 1 | feasible / medium | 3 |
| V4 | `a08b6635a1a74e7b8a37a540e16ade78` | Měření kvality odpovědí chatbota | 2 / done, kolo 1 | unverified / low | 0 |
| V5 | `b25805ed46c943759cfac5e379750894` | 3.5 lokátor chunku: rozdělení karty a ověření proti main | 2 / done, kolo 1 | feasible / medium | 1 |

Společný rodič je `0269aac983774760a05b26c907abf22a`. V1 má feedback `73af1d0378f049a4bdad750fa3684ab4`: human, verdict `agree`, prázdný text, vztah k revizi 2, čas `2026-10-30T09:53:57.492464+00:00`. Human potom vytvořil revizi 3, čas `2026-10-30T09:54:39.530121+00:00`, poznámka „Další kolo výzkumu podle zpětné vazby.“ Nelze zaměnit souhlas s předchozím výsledkem za dokončení druhého kola ani za přijetí libovolné nové produktové migrace. V2–V5 nemají v této tabulce feedback.

Počet evidence není počet ověřených tvrzení: například V4 má dokončený běh a současně výslovně neověřený výsledek. Historický JSON obsahuje i interní náklady výzkumného stolu; nejsou to náklady odpovědi chatbota AmpleLab.

## V1: již existující izolace, 1024 dimenzí a verze cache

- `database/supabase/migrations/0040_rls_tenant.sql:14` čte `app_metadata.organization_id`, vytváří SELECT politiky pro `authenticated`; `service_role` obchází RLS a backend proto musí dál filtrovat vlastníka. Politika volá `auth_organization_id()` přímo; přínos návrhu `(select auth.jwt())` není v této migraci doložen plánem dotazu. Zkontrolovat skutečné indexy a EXPLAIN pod konkrétní rolí, neduplikovat celou migraci.
- `0041_embedding_1024.sql` již změnila deklarovaný typ na `vector(1024)` a obsahuje destruktivní vynulování starých vektorů pro reindex. Nejde o bezvýpadkové přepnutí sad. `backend/rag/embedding/local_embedder.py:11`, `cohere_embedder.py:11` a test `test_local_embedder.py:55` používají 1024. Starý výsledek V1 o současných 1536 dimenzích je vůči této revizi zastaralý.
- `0044_match_kb_chunks_model.sql:33` a novější `0049_kb_chunks_locator.sql` mají pět argumentů: query_embedding vector, match_project text, match_count integer, match_filter jsonb, match_model text. Aktivují `hnsw.iterative_scan=relaxed_order`, max_scan_tuples 20000, nefiltrují embedding_version. Nefiltrovaná větev materializuje sousedy a znovu řadí vzdálenost; metadatový filtr používá zúžené CTE a přesné řazení.
- `backend/core/knowledge/answer_cache_keys.py:24` již používá `answer:v5:{project}:kv{knowledge_version}:...`; `backend/rag/pipeline/answer_cache_keys.py:15` přidává metodu a hash normalizované otázky. `0042_knowledge_version.sql`, `0043_document_write_bump.sql` existují. Historický závěr „pouze mazání prefixu bez verze indexu“ už nepopisuje tento kód.
- `docs/mereni-k5.md` dokumentuje lokální syntetické měření na pgvector 0.8.2; není potvrzením verze ani výkonu zákaznické DB. `database/measure/test_filtered_hnsw.py:27` ověřuje verzi extension při měření. Cílovou běžící verzi PostgreSQL/pgvector jsme nezjišťovali a nezaměňujeme ji za webovou nejnovější verzi. `uv.lock` deklaruje supabase/postgrest/supabase-auth 2.32.0, FastAPI 0.142.2, Redis klient 8.1.0; to nedokládá nainstalovaný server.

Návrh rozhodnutí: zachovat nynější 1024/RLS/cache kontrakty, oddělit revizní audit nasazení a výkonu od případné změny `halfvec`. Navazující ohraničená práce: ověřit dvě organizace a service-role aplikační filtr; získat verzi extension a EXPLAIN pro aktuální RPC; ověřit souběh reindexace a cache verze. Halfvec pouze jako porovnání na kopii s totožnými dotazy/recall, nikoliv automatická migrace. Běh V1 zůstává assigned/kolo 2.

## V3: sady embeddingů nejsou implementovaná přijatá architektura

V prohledaných `backend/` a `database/` nejsou `kb_chunk_vectors` ani `active_set_id`. `database/supabase/supabase_storage.py:1851` ukládá embedding, model a verzi in-place do kb_chunks. `search_chunks:1794` posílá model, nikoliv verzi/sadu; `RetrievalService.retrieve:96` používá nakonfigurovaný embedder. Existuje tedy filtrování modelu a detekce potřeby reindexu, nikoliv ověřené přepnutí dvou sad za běhu.

Zachovat obě původní varianty: vedlejší `kb_chunk_vectors(chunk_id,set_id,embedding)` versus další sloupec `embedding_v2`. Stejná dimenze dovoluje porovnat dva modely v oddělených sadách, ale jejich vektory nejsou navzájem zaměnitelné. Změna dimenze vyžaduje kompatibilní ukládání, indexování i dotazový embedding; pevný sloupec vector(1024) sám jiné dimenze nepřijme. Původní kategorická formulace výzkumu o nové signatuře RPC kvůli typmodu není bezpečný závěr: komentář aktuální 0044 upozorňuje, že PostgreSQL argumentový typmod nevynucuje; řešit konkrétní kontrakt sloupce, indexu a validace.

Návrh rozhodnutí, dosud nepřijatý: revizně připnutá sada s atomickým přepnutím ukazatele je kandidát, ne současné chování. Před implementací vymezit jednu vs. více dimenzí a retenční pravidlo. Dílčí návrhy úkolů: (1) testovací kontrakt stejné/jiné dimenze a EXPLAIN parametrického filtru; (2) návrh schématu a read/write pinning bez míchání sad; (3) backfill + readiness gate počtu/úplnosti/kvality; (4) transakční přepnutí a rollback se souběžnými dotazy a cache revizí; (5) teprve po přijetí retence bezpečné odstraňování. Neopakovat již existující prostou migraci na 1024.

## V4: měření už má konkrétní implementaci, jeho význam má hranice

`backend/rag/pipeline/answer_pipeline.py:425–461` vytváří Interaction s ID, project_id, session_id, otázkou, metodou, zdroji, latencí, odpovědí, tokeny, modely, cost_usd, fallback a citations_check. Selhání telemetry zápisu vrací None, odpověď má přednost. `backend/rag/pricing/query_metrics.py:47` sčítá duration_ms událostí po krocích; usage čte z generation; chybějící telemetry/cena zůstává None. Cache hit má cenu API 0 a žádné nové tokeny, není to nulová cena infrastruktury.

`backend/rag/pricing/query_pricing.py:6` obsahuje statický ceník s datem 2026-10-09 a odhad embeddingových tokenů z délky otázky (3 znaky/token). Cost tedy není čistě měřená faktura a musí nést způsob výpočtu/verzi ceníku. Záznam nyní nese modely, nikoliv samostatnou revizi ceníku, promptu či aktivní sady; tyto vazby jsou konkrétní mezera.

`check_citations` v answer_pipeline.py:90 kontroluje příslušnost citovaných document_id mezi retrieved chunky a platnost číselného odkazu calloutu. Nedokládá pravdivost tvrzení nebo významovou oporu citované věty. Bez citací vrací checked=0 a ok=true; agregát ok nelze bez vysvětlení nazývat přesností odpovědi. Cache hit má citations_check=None. Relevantní testy: `backend/rag/pipeline/test_interaction_record.py`, `test_answer_pipeline.py:734`.

`backend/core/monitoring/monitoring_service.py:46–86` agreguje projekt/časové okno: percentily, náklady a počty změřených položek, tokeny, fallback, citation checks. `frontend/project/monitoring/monitoring-page/components/MonitoringPage.tsx:92` vysvětluje nezměřené „—“. Existuje `backend/rag/evaluation/vysocina_eval_set.json`, verze vysocina-eval/1, konkrétní projekt `117b5c8f-5d43-4264-9717-046766c5fc14`, a uložené reporty. Nejsou univerzální referenční sadou každého projektu. Žádný produkční počet, latence, cena či přesnost nebyly v tomto auditu měřeny.

Návrh rozhodnutí: zachovat online telemetry; rozlišit změřený čas/tokeny, odhad ceny, mechanickou validaci citací a hodnoticí kvalitu. Úkoly jen pro mezery: připnout konfiguraci/ceník/revizi sady do metrik; pokrýt výpadek zápisu a pozorovatelnost ztracené telemetry; popsat jmenovatele a nulové citace; vytvořit/odsouhlasit projektovou eval sadu. Poslední úkol neblokuje první tři. Starý V4 běh zůstává done/unverified, aktuální kód je nový podklad, nikoliv zpětné přepsání historie.

## V5: lokátory jsou přeneseny do retrievalu, dokončení citace vyžaduje vlastní ověření

`backend/core/knowledge/knowledge_types.py:39–53` KbChunk již nese nullable section_id/page_number/source_url/anchor; `:78–93` RetrievedChunk má section_id a PageRef. `backend/rag/indexing/indexing_phase.py:59–62` je přenáší z DerivedChunk. `0025_derived.sql:147–167` obsahuje lokátory odvozené vrstvy a vazbu sekce na dokument.

Pozdější `0049_kb_chunks_locator.sql:24–59` přidává nullable sloupce do kb_chunks, backfill podle chunk_id=id a znovu vytváří pětargumentovou RPC s rozšířenou návratovou tabulkou. Číslo 0045 navrhované starým výzkumem již patří semantic episodes. 0049 zachovává filtr modelu, projektu, stavů i řazení; její samotná existence nedokládá nasazení do DB. SQL v souboru nemá vlastní explicitní BEGIN/COMMIT; bezpečnost drop/create závisí na způsobu spuštění.

`database/supabase/supabase_storage.py:511` mapuje PageRef, `:532` ukládá lokátory, `:1810–1811` je čte přes r.get; stará odpověď RPC tedy zůstává bez lokátorů, místo pádu. `database/test_kb_chunks_locator_contract.py` pokrývá obě úložiště (živý Supabase pouze opt-in), `backend/rag/retrieval/test_retrieval_locator.py:34` porovnává stejné pořadí/skóre s lokátory i bez nich. Testy jsou nalezená evidence, nebyly v tomto read-only auditu znovu spuštěny.

`backend/core/processing/citation_locator.py` umí web/PDF/tabulku a pouze typ pro video (extractor videa není). Nelze tím automaticky prohlásit kompletní cestu RetrievedChunk → konkrétní citace výsledné odpovědi za ověřenou. Návrh úkolu je cílené end-to-end ověření konkrétního odkazu, chybějícího lokátoru, tenant filtru a řazení na nasazené 0049; doplnit pouze prokázanou ztrátu lokátoru. Neduplicovat hotové typy, sloupce ani indexaci.

## Oddělení stavů pro plán

Původní research.status označuje běh; verification/verdict platnost tvrzení; lidský review/přijetí stav rozhodnutí; pracovní task vlastní připravenost a realizaci. Nalezený kód = doložená existence, nikoliv nové přijetí a nikoliv důkaz produkčního nasazení. Všechny nové úkoly v tomto dokumentu jsou návrhy. Neznámá verze DB blokuje ověření nasazení a konkrétní SQL změny, ne čtení kódu, mapování obrazovek ani návrh metrik. Žádný návrh zde není automaticky připravený ke spuštění agenta.

## V2: přesné obrazovky a vazba na aktuální kód

Původní zdroj výzkumník odmítl jako `outside`, proto V2 nese unverified. Soubor je nyní dostupný ke čtení v Downloads, ne jako webový důkaz. Byl dekódován lokální JSON/gzip manifest a template; nebyly prováděny vložené skripty. Přesné názvy sedmi fází ze zdroje: **Sběr dat, Zpracování, Sémantika, Znalostní báze, Ladění, Chatbot, Provoz**.

Níže jsou názvy všech 17 návrhů beze změny. Route i soubor komponenty byly ověřeny proti výše uvedené revizi. Jde o statické mapování, nikoliv prohlášení funkční shody. Zejména SemanticPage.tsx:61 stále ukazuje pro entities/events/episodes/workflow „Zatím bez dat – přináší sektor S“, i když načítá seznam dokumentů a počet větve SEMANTIC. FlowPage načítá structure API, SourceTestPage již volá testovací službu; stará tvrzení V2, že tyto routy vůbec chybí, jsou překonaná. Následný úkol má ověřit interakční stavy proti jednotlivým návrhům a doplnit jen konkrétní mezeru, nikoliv znovu vytvořit sedmnáct stránek.

Source: `C:\Users\Admin\Downloads\AmpleLab – platforma znalostí a chatbota.html`

SHA-256: `6a7ad3f9562be20d1a6b434853f4a35aedccaa9f8838bcfcd0969f6d1420dadc`

| Design | Route | Component file |
|---|---|---|
| Přehled projektu – 7 fází a hlavní metriky | `/projects/:id` | `frontend/project/overview/project-detail-page/components/ProjectDetailPage.tsx` |
| 1 · Sběr dat – RAW zdroje (inventář) | `/projects/:id/sources` | `frontend/project/sources/sources-page/components/SourcesPage.tsx` |
| 1 · Přidat zdroj | `/projects/:id/sources` | `frontend/project/sources/add-source-dialog/components/AddSourceDialog.tsx` |
| 1 · Pracoviště zdroje – web › stránka › znalost | `/projects/:id/sources/:sourceId` | `frontend/project/sources/source-workspace/components/SourceWorkspacePage.tsx` |
| 1 · Pracoviště zdroje – soubor | `/projects/:id/sources/:sourceId` | `frontend/project/sources/source-workspace/components/SourceWorkspacePage.tsx` |
| 2 · Zpracování – tok a Semantic Router (připraveno) | `/projects/:id/processing/flow` | `frontend/project/processing/flow-page/components/FlowPage.tsx` |
| 3 · Sémantika – epizoda a workflow (připraveno) | `/projects/:id/semantic` | `frontend/project/semantic/semantic-page/components/SemanticPage.tsx` |
| 4 · Znalostní báze (připraveno) | `/projects/:id/knowledge` | `frontend/project/knowledge/knowledge-page/components/KnowledgePage.tsx` |
| 5 · Ladění – test zdroje (připraveno) | `/projects/:id/tuning/source-test` | `frontend/project/tuning/source-test-page/components/SourceTestPage.tsx` |
| 6 · Chatbot – playground (připraveno) | `/projects/:id/chatbot/playground` | `frontend/project/chatbot/playground-page/components/PlaygroundPage.tsx` |
| 7 · Provoz – monitoring (připraveno) | `/projects/:id/monitoring` | `frontend/project/monitoring/monitoring-page/components/MonitoringPage.tsx` |
| 2 · Zpracování – oblast Extrakce: Přehled a Karanténa (karta 2.26) | `/projects/:id/processing` | `frontend/project/processing/processing-page/components/ProcessingPage.tsx` |
| 2 · Zpracování – detail zdroje: Extracted, Metadata, Original, History (karta 2.26) | `/projects/:id/processing/sources/:sourceId` | `frontend/project/processing/processing-source/components/ProcessingSourcePage.tsx` |
| 2 · Karanténa – opravit, otestovat, pustit do provozu | `/projects/:id/processing/quarantine` | `frontend/project/processing/quarantine-page/components/QuarantinePage.tsx` |
| 2 · Mapování datové sady – role polí a pravidlo pro provoz (univerzální) | `/projects/:id/processing/datasets/:sourceId/mapping` | `frontend/project/processing/dataset-mapping-page/components/DatasetMappingPage.tsx` |
| 2 · Zpracování – oblast Struktura a klasifikace: Přehled (karta 2.27) | `/projects/:id/processing/structure` | `frontend/project/processing/structure-page/components/StructurePage.tsx` |
| 2 · Zpracování – detail zdroje: Structure a Classification, override a re-run (karta 2.27) | `/projects/:id/processing/sources/:sourceId` | `frontend/project/processing/processing-source/components/ProcessingSourcePage.tsx` |
