# Audit dokončení OporaHubu — 2026-10-21

Audit zachovává původní rozsah: Canvas drží přijatý plán, GitHub kód a Office
vykonává práci. Kontrolovány byly publikované produktové revize Canvas
`90f72b4838a554a53f255e039eb20efae93dc1a3` a Office
`7bc75faa4a9f02c30778efa63915ff601627d9fa`, skutečné dokončené logy a vykreslený
náhled. Tento audit není nové spuštění testů ani prohlášení o dokončení cíle.

**10 hotovo / 2 rozpracováno / 0 nezačato.** Skutečný provozní průchod
nakonfigurovaným poskytovatelem chybí, proto nelze uzavřít body 11 a 12.

## Požadavky a odpovídající důkazy

Testovací soubor určuje rozsah kontroly; její výsledek dokládají níže uvedené
dokončené běhy. Pouhá existence testu se zde nepovažuje za úspěšný výsledek.

| # | Požadavek | Evidence a její meze | Stav |
|---|---|---|---|
| 1 | Neměnné přijaté revize, CAS, přijetí člověkem | [Kontrakt](oporahub.md); `backend/canvas/test_opora_proposals.py`, `backend/api/editor/test_opora_proposal_routes.py`; backendová sada. Rozdílné stale návrhy zůstávají konfliktem, přesný replay vrací původní revizi. | Hotovo |
| 2 | Grafové návrhy, rebase, konflikty | [Změny grafu](oporahub-graph-changes.md); `backend/canvas/test_opora_graph_proposals.py`, `backend/canvas/test_opora_graph_changes.py`. Převod vytváří nové ID a neskrývá konflikt stejné položky. | Hotovo |
| 3 | Office lease, epochy, výsledky, časové rozpočty | [Execution](oporahub-executions.md), [rozpočty](oporahub-execution-budgets.md); `backend/canvas/test_opora_executions.py`, `backend/canvas/test_opora_execution_budgets.py`; skutečný Office→Canvas průchod. Časové oprávnění samo neprokazuje izolaci. | Hotovo |
| 4 | GitHub důkazy a trvalá rekonciliace | [Kontrakt rekonciliace](oporahub-reconciliation-contract.md); `backend/canvas/test_opora_reconciliation_manager.py`, `database/repositories/test_opora_reconciliation_jobs.py`. Přijetí plánu, merge, ověření a nasazení jsou různé stavy; GitHub a Canvas nemají společnou transakci. | Hotovo |
| 5 | Jednostránkový přehled a skutečný Claude návrh | [Klikací artifact a původ](design/README.md), [živé rozhraní](oporahub-overview.md); finální browser důkaz light/dark/mobil, přesný výběr a Esc/fokus. Ukázková data návrhu nejsou stavem aplikace. | Hotovo |
| 6 | Zachování dat, historie, archivace, obnova | `database/repositories/test_opora_context_events_migration.py`, `backend/canvas/test_opora_execution_budget_restore.py`; backendová sada. Historie ani soukromé piny se nemažou; změna DDL coverage v2 odmítne práci bez automatického resetu nebo re-enrollmentu. Produkční migrace nebyla provedena. | Hotovo |
| 7 | Příprava Lean/TLA+ a skutečný TLC důkaz | [Evidence formální kontroly](oporahub-verification.md), [model a meze](../tools/formal/oporahub-execution/README.md), [výsledek TLC](../tools/formal/oporahub-execution/result.json). Raw logy byly nalezeny a hashově ověřeny. Lean runtime ani důkaz implementace netvrdíme. | Hotovo |
| 8 | Sparse context v2 | [Kontrakt](oporahub-sparse-context.md); `backend/canvas/test_opora_execution_context_edges.py`, `database/repositories/test_opora_execution_contexts_replay.py`; skutečný HTTP průchod v2. Vnější soubory a obsah síťových referencí nejsou skrytě vydávány za zachycený kontext. | Hotovo |
| 9 | Verze textu, kresby a konfigurace | [Obsah 2b](oporahub-content-changes.md); `backend/canvas/test_opora_content_sources.py`, `backend/canvas/test_opora_content_durability.py`; backendová sada a dřívější browser důkaz. První přijetí výslovně přebírá celý základ. | Hotovo |
| 10 | Komentáře, riziko, přesné potvrzení přijetí | [Review 3b](oporahub-proposal-review.md); `backend/canvas/test_opora_proposal_review_service.py`, `backend/canvas/test_opora_proposal_acceptance_guard.py`; API a browser všech čtyř druhů návrhů. Lokální jméno není nezávislá lidská identita. | Hotovo |
| 11 | Izolovaný vykonavatel a podepsaná spotřeba | [Kontrakt 5b](oporahub-isolated-execution.md), [Office provozní nastavení](https://github.com/Pletor/agent-office/blob/7bc75faa4a9f02c30778efa63915ff601627d9fa/docs/opora-isolated-execution.md); 43 cílených Office testů a skutečný Office→Canvas HTTP průchod se syntetickým providerem. Provozní izolace, autentická usage a ukončení u živého poskytovatele nejsou ověřené. | Rozpracováno |
| 12 | Závěrečný audit, docs, testy, vizuální důkaz, PR | Tento audit, propojené kontrakty, oba otevřené PR a read-only náhled. Implementační důkazy jsou hotové; provozní důkaz bodu 11 chybí. | Rozpracováno |

## Co skutečně proběhlo

- Canvas backend/database: **3 313 PASS / 4 skip / 1 fail**. Jediná chyba je známý
  Graphify baseline `test_map_refresh.py` (unavailable místo watching). Nové
  observer kontroly mají 37 cílených úspěchů; celá sada není zelená.
- Finální frontend: **229 souborů / 1 595 PASS**. TypeScript, Vite i kopie fontů
  dokončeny. PowerShell obal vrátil 1 kvůli stderr varování Vite; není vydáván za
  čistý exit ani za zaznamenanou chybu sestavovacích fází.
- Office: **43 cílených PASS**, typecheck a build PASS. Standardní celý test
  překročil 150 sekund. Omezená diagnostika: 750 PASS / 23 fail / 7 cancel / 1 skip.
  Z 30 neúspěšných položek je 28 sdílených s baseline. Dvě kandidátní file timeout
  odchylky samostatně prošly na kandidátovi i čistém baseline (20/20 na každém).
  To neprokazuje zelenou celou sadu ani příčinu odchylek.
- Skutečné Office služby a routy volaly skutečný Canvas přes HTTP pro context v1
  i v2 a budget v2: podpis, 187 centů / 342,5 aktivní sekundy, následný heartbeat,
  přesný native receipt, ukončovací readback a obnova bez nového běhu. Jen provider
  byl syntetický. Produkční route registry je propojená s instancí služby ve Floor;
  nejde pouze o samostatnou testovací factory.
- TLC raw logy odpovídají hashům v publikovaném výsledku: pozitivní průchod má
  53 959 661 generovaných / 1 484 052 odlišných stavů, hloubku 12 a prázdnou frontu.
  Negativní profily odhalily přesně `OneActiveOwner` a `NoStaleEpochReceipt`.
  Výsledek platí jen pro uvedený konečný model, ne automaticky Python/TypeScript.
- Read-only náhled produktové revize na loopback portu 18773 používá kopii
  syntetických dat. Sedm reprezentativních změnových POST vrací 403. Browser:
  light/dark/mobil, žádný vodorovný přesah ani JS chyba, právě jeden vybraný detail,
  Esc vrací fokus. Samostatný zapisovatelný fixture průchod předtím ověřil oba
  případy zachovaného filtru A → jiný observer B bez cizího native detailu.
- Root Ruff má 56 shodných výchozích nálezů; nové backendové moduly jsou čisté.
  Dřívější porovnání docs/struktury nepřidalo dluh ani nezvýšilo limity.

## Identita lokálních důkazů

Níže jsou SHA256 dokončených lokálních souborů z vývojového Temp adresáře.
Soubory nejsou součástí repozitáře; hash je identifikuje, sám neprokazuje správnost
ani důvěryhodný původ. Raw TLC logy jsou také v externí cache; jejich názvy a hashe
jsou v přibaleném výsledku. Tato kontrola je četla, model znovu nespouštěla.

| Soubor | SHA256 |
|---|---|
| oporahub-observer-root-backend-full.log | `5a6c439b5d6d513d828ace82c9966c8dab8b8eebe2b0486868f04e70c1a7a34b` |
| oporahub-observer-final-frontend.log | `8cf5c5fc5f0862f086a434d56e00047a2e45a30ab03621ea3795b927f77d7778` |
| oporahub-observer-final-build.log | `f24e7c61e13f84c0dd2427c5788f0fcfe78bfc276bcf9ee0c225007f13e4dacf` |
| oporahub-executors-focused-final.log | `12e57a3f9b4109785fc65042c72e4d8bb91892aa77dcbc5dfc5f8fcaa5ac6771` |
| oporahub-executors-typecheck-final.log | `8854337b462f5c784fc146dc10ba5450f6e5feee9cc40f99d2082b9996758a14` |
| oporahub-executors-root-build.log | `4d4aab00cbae670e95dd4850394adde431be88e9292399e566cac3288c41bbfb` |
| oporahub-executors-bounded-comparison.json | `31ae15ca71eb4720ae40db97a86abccc1211d97d450b826fcfd1006e5bbd3989` |
| oporahub-isolated-real-canvas-smoke-result.json | `ace5fba802189cebb9a4504bb92fc273bffa869fa91da6d6446ad85a369550ed` |
| oporahub-observer-readonly-preview-result.json | `d02327f1b6a9b3d183796d75afc31663e811a789ca9a92184e75a17896818a1e` |

## Zbývající provozní průchod

Kontrola přítomnosti nastavení v Process/User/Machine prostředí nenašla žádnou
z 11 požadovaných Office proměnných ani Canvas `OPORA_EXECUTION_OBSERVERS`.
Žádné hodnoty tajemství se nečetly. Existující CLI přihlášení tento účet nenahrazuje.

Další krok je nastavit dokumentovanou služební konfiguraci v serverovém prostředí
a provést omezený průchod na živém provideru: připnutý kód/agent/prostředí,
ověřená izolovaná session, práce pod původním oprávněním, odebrání oprávnění,
doložené ukončení a autentické kumulativní API usage včetně pozdního odečtu.
Zachovat intent, původní mapping a receipt; obnova nesmí vytvořit náhradní běh.
Bez tohoto důkazu zůstává goal aktivní a nelze tvrdit provozní izolaci ani SLA.
Ceníková spotřeba se ani pak nesmí vydávat za fakturu či přesný finanční hard cap.

Audit neprovedl merge, deploy, placené provider volání, produkční migraci ani
změnu globálních ochran. Není žádný nevyřízený požadavek na obecný souhlas.
