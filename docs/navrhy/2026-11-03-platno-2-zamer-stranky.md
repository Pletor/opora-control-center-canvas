# Plátno 2: záměr stránky

Druhé patro nového základu (`docs/navrhy/2026-11-03-novy-zaklad.md`, artefakt „Cesta OPORY“). Plátno 2 popisuje, co stránka dělá: odkud uživatel přijde, co vidí, co udělá, jak systém odpoví, jaká data vzniknou a kdy je hotovo. Srdce navrhuje verzi a člověk ji schvaluje. Všechno pod plátnem 2 je autonomní: srdce schválený záměr rozloží do technického plánu a běžící aplikace se proti němu ověří.

**Hotovo, když** srdce schválený záměr stránky rozloží do technického plánu a běžící aplikace projde workflow tak, jak je nakreslené.

## 1. Co už existuje (průzkum 2026-11-03)

- **Stránka** je uzel architektury se `site.kind = "page"` (`backend/canvas/site_metadata.py`: `path`, `goal`, `feel`, `navLabel`, `sections`). Editor je `frontend/project/architecture-editor/` (`domain-map/PageIntentFields.tsx`, `page-sections/`).
- **Cesty zákazníka** mezi stránkami: `site.journeys` aplikace, plán přehrání `GET /api/project-architecture/journey-plan`, runner `tools/journey_run.py` (Playwright) a doklad `POST /api/project-architecture/journey-runs` (`opora.journey-run/1`, ověřuje jen přechody `from → to`).
- **Engine toků** `backend/flow/` už zná `kind = page_intent` (`workflows.py`), ale nic ho nepoužívá. Workflow patří jen projektu. `approval.human` čeká jako běh a k aktivaci verze nevede.
- **Sdílený editor** `frontend/shared/flow-editor/` je generický. Plátno srdce `frontend/project/heart-canvas/` se otevírá přes `projectView=heart`.
- **Srdce** ve snímku vidí stránky jen jako `{id, name, path, goal, feel}`.
- **Globální nastavení webu a design** (SEO, GDPR, e-mail, hlavička a patička, typografie) v OPOŘE neexistují.

## 2. Model

- **Vlastník workflow:** `flow_workflows.owner_ref` (text, NULL). Formát je `opora:page:<nodeId>`. Na jedno `(project_id, kind, owner_ref)` připadá právě jedno workflow. Srdce (`kind = heart`) má `owner_ref` NULL.
- **Katalog `page_intent`:** typy uzlů jen pro záměr, vrací je `GET /api/flow/node-types?kind=page_intent`. Bez parametru vrací typy plátna 1 jako dnes. Dílek pozná druh plátna jen z `kind`.

| Typ | Co říká | Klíčové parametry |
|---|---|---|
| `intent.entry` | Odkud uživatel na stránku přijde | `from` (stránka, odkaz, kampaň), `actor` |
| `intent.view` | Co vidí, s vazbou na sekci stránky | `section` (id sekce), `shows` |
| `intent.action` | Co udělá | `do` (`open` / `click` / `type` / `submit`), `section`, `text?` |
| `intent.reaction` | Jak systém odpoví | `does` (`show` / `navigate` / `send_email` / `store` / `call`), `expect` (ověřitelný popis) |
| `intent.data` | Data, která tečou | `fields: [{name, type, required}]`, `to` (kam data jdou) |
| `intent.done` | Kritérium dokončení | `claim` (ověřitelné tvrzení), `check` (`visible` / `path` / `request` / `email` / `record`) |
| `intent.error` | Chybová větev | `when`, `shows` |

  Porty: tok `main` (in/out) a data `data` (in/out). Vazby `main` tvoří tok uživatele, vazby `data` tvoří tok dat. Pravidla vazeb hlídá `graph_check.py`.
- **Záměr se nespouští.** Workflow `page_intent` nemá běhy ani plánovač. `POST /versions/{id}/runs` na něm vrací 409 `not_runnable`.

## 3. Schválení

- Srdce (token srdce) nebo člověk uloží draft a navrhne kandidáta (`/api/flow/workflows/{id}/versions`, `/versions/{id}/candidate`).
- **Aktivaci kandidáta `page_intent` dělá jen člověk:** `POST /api/flow/versions/{id}/approve` s doklady UI. Volání `activate` na `page_intent` vrací 409 `approval_required`. `POST /versions/{id}/reject {reason}` vrátí kandidáta do stavu `retired` s důvodem v logu. Schválení i zamítnutí jdou do `flow_log_events` (`canvas = 2`) s autorem.
- Uzel `approval.human` zůstává pro workflow plátna 1. Na plátně 2 se schvaluje přechodem verze.

## 4. Srdce

- **Snímek** má sekci `ZÁMĚRY STRÁNEK`: u každé stránky stav (`bez záměru`, `čeká na schválení`, `schválený vN`, `zastaralý`, tedy stránka se změnila po schválení) a počet kritérií `intent.done`.
- **Nástroj** `opora_heart.py intent`:
  - `show PAGE` vypíše aktivní a kandidátní verzi kompaktně;
  - `propose PAGE --file F` uloží draft a navrhne kandidáta, `--dry-run` jen ověří graf;
  - `diff PAGE`.
- **Rozklad:** srdce plánuje karty stránky ze schválené verze. Kritérium `intent.done` je fakt z grafu: ticket karty, která ho naplňuje, nese v `machine.intent` `{workflowVersionId, nodeIds}` a server do `doneCriteria` doplní `claim` z těch uzlů. Srdce je do těla nepíše.

## 5. UI

- `projectView=intent&page=<nodeId>` otevře plátno záměru stránky: sdílený `FlowEditor` s katalogem `page_intent`, lištu verzí (aktivní, kandidát, rozdíl) a pro člověka tlačítka Schválit a Zamítnout. Zamítnout chce důvod.
- Vstup z karty stránky (`PageCard`) a z editoru stránky je tlačítko „Záměr“ s odznakem stavu ze snímku: bez záměru, čeká, schválený, zastaralý.
- `map_check` přidá pravidla `page.no-intent` a `page.intent-stale`.

## 6. Ověření běžící aplikace

- `GET /api/project-architecture/intent-plan?page=<nodeId>` odvodí z aktivní verze plán přehrání: kroky z `intent.action`, očekávání z `intent.reaction` a `intent.done`, selektory přes `data-opora-section`. Plán má `digest` verze.
- Runner `tools/journey_run.py --intent PAGE` přehraje plán (Playwright) a odevzdá doklad `opora.intent-run/1` přes `POST /api/project-architecture/intent-runs`: `{pageId, workflowVersionId, digest, nodes: [{nodeId, ok, reason?}]}`. Doklad starší verze je zastaralý.
- Neprošlé uzly se zapíšou do `flow_log_events` (`canvas = 2`, `kind = intent.failed`) a probudí srdce stejně jako jiné chyby pláten. K tomu vznikne vstup logu pláten 2–4: `POST /api/flow/log`, s tokenem srdce nebo dělníka téhož projektu.

## 7. Globální nastavení a design webu

Globální nastavení a design webu řeší kontrakt [Správa webu a Design systém](2026-11-04-sprava-webu-design-system.md); tenké nastavení z #282 je smazané.

## 8. Vlak PR

1. **P2-1 engine:** `owner_ref`, katalog `page_intent` s filtrem `kind`, `not_runnable`, `approve`/`reject` a `approval_required`. Jen backend, s testy.
2. **P2-2 UI:** plátno záměru, Schválit a Zamítnout, vstup z karty stránky, odznak. Závisí na P2-1.
3. **P2-3 srdce:** snímek `ZÁMĚRY STRÁNEK`, nástroj `intent`, `machine.intent` a doplnění `doneCriteria`. Závisí na P2-1. Prompt srdce se mění jen přes Brain a eval.
4. **P2-4 ověření:** `intent-plan`, runner `--intent`, `intent-runs`, `POST /api/flow/log`. Závisí na P2-1.
5. **P2-5 nastavení webu:** `site` nastavení, editor na stránce Projekt a čtení srdcem. Nezávislé.

Po každém PR: `uv run pytest` (cíleně), `npm test`, `npm run build`. Měřítko hotovo se ověří na pískovišti, protože vývoj Ample je zastavený a Ample stránku Kontakt nemá: založí se stránka `/kontakt` se záměrem „kde sídlím s mapou, rychlé spojení, formulář na e-mail“.
