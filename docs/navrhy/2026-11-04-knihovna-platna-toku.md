# Knihovna komponent: plátna toků dat (nový bod 5 z M1)

**Zadání:**
- obrázky `image5.png` (plátno 2), `image6.png` (panel Komponenty), `image7.png` (paleta a AI agent n8n) a `image8.png` („Canvas s logikou: jak tečou data… stránka, aplikace nebo komponenta má vlastní workflow“);
- odpovědi člověka z 2026-11-04;
- rešerše n8n (`research-n8n`, docs.n8n.io + živá šablona RAG 16963).

Nahrazuje §0 bod 5 kontraktu `2026-11-04-sprava-webu-design-system.md`, kde panel Komponenty byl jen „seznam předloh“.

**Princip:**
- Karta v panelu Komponenty je **složka** (Databáze, Backend, AI a RAG…).
- Ve složce jsou **plátna toků** typu 2. Každé rozkresluje jednu metodu, funkci nebo princip do nejmenšího detailu: co se musí stát, v jakém pořadí, za jakých podmínek, jaká data tečou dovnitř a ven a co se stane při chybě.
- Plátno je uložené v knihovně **napříč projekty** a dá se znovu použít jinde.

**Hotovo, když:**
1. V Architektuře otevřu složku „AI a RAG“ a založím v ní plátno „RAG – ingest a dotaz“.
2. Nakreslím na něm tok jako v image8:
   - rámec „Ingest“: spouštěč → načtení → dělič → embedding → vektorové úložiště;
   - rámec „Dotaz“: chat → agent s porty Model, Memory a Tool → odpověď.
   - Každý uzel má popis, schéma vstupu a výstupu, ukázková data a chování při chybě.
3. Z jiného projektu plátno vezmu jako odvozenou kopii, upravím ji a uložím zpět jako vylepšený prvek. Prvek ví, z čeho vychází, a původní prvek ukazuje, že má novou odvozenou verzi.
4. Srdce (LLM) plátno přečte, navrhne do něj změnu a vlastní plátna si ukládá do knihovny agenta.

## 0. Milníky (stavět jen milník, po kontrole člověkem jít dál)

- **K1, model a engine** (backend, bez UI): knihovna, složky, plátna, rodokmen, katalog „toky dat“, rámce a poznámky v grafu, kontrola grafu, API. Kontrola proběhne přes API a testy.
- **K2, plátno a panel** (frontend): složky v panelu Komponenty, plátno s paletou podle n8n, rámce, poznámky a inspektor uzlu, převzetí do projektu a uložení vylepšení. Kontrola v prohlížeči proti image7 a image8.
- **K3, LLM:** srdce čte a navrhuje, má knihovnu agenta, snímek knihovny a ovládání plátna pro LLM.
- **Až po schválení K1–K3:** jeden společný katalog pro záměr stránky i knihovnu. Dnešních 7 uzlů `intent.*` se převede do katalogu „toky dat“.

## 1. Model

**Knihovna** je globální, bez `project_id`. Má dvě části:
- **Člověk:** píše člověk.
- **Agent:** píše srdce a dělníci. Člověk ji čte a může z ní prvek povýšit do části Člověk.

**Složka:** `{id, owner: human|agent, slug, title, description, order}`.
- Výchozí složky člověka mají stejné kategorie jako dnešní panel: Databáze, Backend, DevOps, Cache, Docker, Funkce a metody, Infrastruktura, Security, Monitoring, Testy, Autentizace, Fronta a události, Úložiště, Notifikace, Platby, AI a RAG a další.
- Složky Skills, Tools a Harness zůstávají odkazem do Brainu, jak jsou dnes.

**Plátno toku** je workflow flow enginu:
- `kind = library_flow`, `project_id = NULL`, `owner_ref = opora:library:<owner>:<folder>/<slug>`;
- verze `draft → active` s historií a návratem, jak je dnes;
- změny volně: kdo smí do dané části knihovny psát, uloží a aktivuje bez schválení.

**Rodokmen:** verze nese `derivedFrom: {workflowId, versionId}`.
- **Převzetí do projektu** vytvoří kopii: `kind = library_flow`, `project_id = <projekt>`, `owner_ref = opora:project-flow:<nodeId|slug>`, s `derivedFrom` na knihovní verzi. Projekt kopii mění sám.
- **Uložení vylepšení** vytvoří v knihovně **nový prvek** s `derivedFrom` na kopii v projektu.
- Původní prvek dál drží hlavní slovo. Jeho detail ukáže seznam odvozených prvků a projektů, které ho používají.

**Graf** (`FlowGraph`) přidává k `{nodes, edges}` dvě pole:
- `notes[]`: `{id, content (markdown), x, y, width, height, color}`. Je to obrys nebo rámec za uzly a vychází z n8n sticky note.
- `groups[]`: `{id, name, description ≤ 145, nodeIds[], inputSchema?, outputSchema?}`. Vychází z n8n Canvas Groups. Platí tato pravidla:
  - uzly tvoří souvislý řetězec;
  - vstup vede jen do prvního a výstup jen z posledního uzlu;
  - AI uzel je ve skupině spolu se svými sub-uzly;
  - skupina neobsahuje spouštěč.

  Skupinu jde sbalit do jednoho uzlu, takže se dá zanořit od metody ke krokům.

**Uzel** k dnešním `type` a `params` přidává:
- `notes` a `notesInFlow` (podtitulek na kartě);
- `inputSchema` a `outputSchema` (JSON Schema nebo příklad);
- `example` (ukázková data, obdoba pinData);
- `mode: perItem | once`;
- `onError: stop | continue | errorOutput` a `retry {maxTries, waitMs}`.

Hrana se klíčuje podle **id** uzlu, ne podle jména.

## 2. Katalog „toky dat“ (porty a paleta podle n8n)

**Data:** po `main` teče `Item[] = {json, binary?, pairedItem?}`. Uzel běží pro každou položku, s `mode: once` jen jednou. Sub-uzly pracují s první položkou a karta to ukazuje.

**Porty:**
- `main`: vstup vlevo, výstupy vpravo. Výstupy mohou mít popisek, například true/false, loop/done, větve Switch, nebo error.
- Sub-porty dole, spojení vede vždy ze sub-uzlu do kořenového uzlu: `model`, `memory`, `tool`, `outputParser`, `embedding`, `document`, `textSplitter`, `retriever`, `vectorStore`, `reranker`.
- Port má `{type, label, required, maxConnections}`. Porty závisí na parametrech, proto je počítá funkce `ports(params)`. Příklad je vektorové úložiště v režimu insert a v režimu nástroj.

**Paleta:** kategorie podle n8n.
1. Spouštěče
2. AI: Agent a Řetězce, pod nimi Modely, Paměť, Nástroje, Vektorová úložiště, Embeddingy, Načítače, Děliče, Parsery, Retrievery
3. Akce ve službě (DB, API, soubor)
4. Transformace dat
5. Tok
6. Jádro
7. Lidská kontrola
8. Poznámka a rámec

Klik na „+“ u portu otevře paletu zúženou na typ portu.

**Typy uzlů ve verzi v1 (asi 22):**

| Kategorie | Uzly |
|---|---|
| Spouštěče | `trigger.manual`, `schedule`, `webhook`, `chat`, `form`, `subflowInput`, `evaluation` |
| Transformace | `transform.set`, `transform.code` |
| Tok | `flow.if`, `switch`, `merge`, `loop`, `wait`, `subflow`, `stopError` |
| Akce | `action.http`, `action.db`, `action.file` |
| AI | `ai.agent`, `ai.chain`, `ai.model`, `ai.memory`, `ai.tool`, `ai.vectorStore`, `ai.embedding`, `ai.documentLoader`, `ai.textSplitter`, `ai.retriever`, `ai.outputParser` |
| Lidská kontrola | `human.approval` |

Porty a parametry jednotlivých uzlů jsou v tabulce C rešerše.

Plátno toku se **nespouští**. Popisuje, jak má věc fungovat, a ověřuje se kontrolou grafu.

**Kontrola grafu** (stejná jako n8n, odmítne už při tažení):
- nepřipojený povinný sub-port;
- překročený `maxConnections`;
- nekompatibilní typ portu;
- skupina, která porušuje pravidla;
- odkaz `$('uzel')` na uzel, který neexistuje.

## 3. API (K1)

| Cesta | Co |
|---|---|
| `GET /api/library?owner=human\|agent` | Složky a plátna (titulek, popis, aktivní verze, počet odvozených) |
| `POST /api/library/folders`, `PATCH`, `DELETE` | Složka. Do části člověka píše člověk, do části agenta agent a člověk |
| `POST /api/library/flows {folder, slug, title}` | Založí plátno (`library_flow`) |
| `GET /api/library/flows/{id}` | Detail: verze, rodokmen (z čeho vychází, kdo z něj vychází), projekty, které ho používají |
| `POST /api/library/flows/{id}/adopt {project, nodeId?}` | Převezme plátno do projektu jako odvozenou kopii |
| `POST /api/library/flows/{id}/contribute {folder, slug, title}` | Kopii z projektu uloží do knihovny jako nový prvek |
| `POST /api/library/flows/{id}/promote` | Přesune prvek z knihovny agenta do knihovny člověka, smí jen člověk |
| Flow engine `/api/flow/...` | Verze a graf, beze změny tvaru. `node-types?kind=library_flow` vrací katalog, `graph-check` kontroluje graf |

## 4. Rozhraní (K2)

- **Panel Komponenty** má přepínač knihovny Člověk a Agent. Karty jsou složky s počtem pláten a „+ Složka“. Klik na složku otevře její obsah: karty pláten s titulkem, popisem, verzí a rodokmenem, plus „+ Nové plátno“.
- **Plátno** je sdílený `FlowEditor`, stejný jako u pláten 1 a 2. Přibude:
  - paleta s kategoriemi n8n a hledáním;
  - rámce a poznámky;
  - sbalení skupiny;
  - inspektor uzlu se záložkami Parametry, Data (vstup, výstup, příklad), Chyby a Poznámka;
  - lišta verzí;
  - akce „Převzít do projektu“ a „Uložit jako vylepšení“.
- **V projektu** je převzaté plátno vidět u domény nebo stránky (místo upřesní K2). Ukazuje „vychází z <prvek>@<verze>“ a upozorní na novější verzi v knihovně.

## 5. LLM (K3)

- **Snímek srdce:** sekce `LIBRARY` se složkami, plátny a verzemi. Srdce si načítá jen to, co potřebuje.
- **Nástroj srdce:** `opora_heart.py library show|propose|save`.
  - `save` píše do knihovny agenta přímo.
  - `propose` k plátnu člověka vytvoří draft a člověk ho přijme jedním klikem.
- **Učení:** plátno agenta nese `learnedFrom` (projekt, karta, výsledek). Když se ověří v projektu, srdce navrhne povýšení do knihovny člověka.

## 6. Mazání a přestavba

- Z panelu Komponenty zmizí karty předloh a prohlížeč `CatalogFamilyViewer` (to je ten seznam). Statický katalog `library-catalog` zůstává jen pro vkládání předloh v Editoru stránky.
- Kind `brain_workflow` se nepoužívá a uvolní místo pro `library_flow`. Změna CHECKu potřebuje přestavbu tabulky `flow_workflows`, migrace jde v K1.

## 7. Otevřené otázky (rozhodne člověk při schválení)

1. Kde je převzaté plátno v projektu vidět: u domény, u stránky, nebo na obou místech?
2. Má se jedna složka moci zanořit do druhé (Backend → Autentizace)? Doporučení: ne, stačí jedna úroveň a štítky.
3. Má být import a export ve formátu n8n JSON hned v K1, nebo až později? Doporučení: až později.
