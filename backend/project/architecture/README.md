
## Stav webu (`web_status.py`)

Služba kontroluje HTTPS dostupnost hostů domén projektu (`docs/domeny-a-worktree.md` §8). Hosty bere jen z grafu
(aplikační uzly `site.kind == "application"`, jejich prostředí, volitelně `site.healthPath`); požadavek `GET
/api/project-architecture/web-status?project=&domain=&refresh=` žádnou URL nenese. Kontrola běží na dotaz s cache
60 s na host, ruční `refresh` nejdřív po 30 s, nejvýš 4 souběžné kontroly a 20 hostů na projekt (ostatní jsou
`unchecked`). Samotné spojení dělá `backend/integrations/web_probe_client.py` (bez proxy, bez sledování
přesměrování, odmítá privátní adresy a připíná spojení na ověřenou IP). Výsledky jsou jen v paměti.

## Stav práce (`work_status.py`)

`GET /api/project-architecture/work-status?project=` (`docs/domeny-a-worktree.md` §7, §9) skládá stav každého worktree
ze tří zdrojů: relace asistenta, hook bindingy a lease + aktivita karet. Vyhrává nejvyšší stav (běží > čeká > stojí >
bez relace), `reasons[]` nese důvody vítězného stavu. Prahy: hook bez signálu 120 s, aktivita karty 300 s, okno „stojí“
24 h. Worktree se řadí do domén podle `workspaces.node_id`; co nesedí na žádnou doménu architektury, je v `unassigned`.
Relace v `main`/`draft` jsou v `mainSessions`. Čisté funkce berou `now`; čtení zdrojů je v `collect_sources`.

## Kontrola mapy (`map_check.py`)

`GET /api/project-architecture/map-check?project=` (`docs/architektura-pro-agenty.md` §5) vrací
`{findings: [{rule, nodeId|edgeId|journeyId, message}], summary: {pravidlo: počet}}` nad přijatým grafem (architektura složená
s obsahem `main`, bez Gitu `draft`; čte ho `work_status.architecture_graph`). Bez modelu, deterministicky: pořadí
pravidel, pak id. Pravidla `journey.broken`, `journey.unrealized`, `journey.via-unknown` (sekce signálu přechodu,
kterou stránka předchozího kroku nemá), `journey.unverified` (cesta bez prošlého a aktuálního dokladu přehrání;
jen při čtení, doklady načte `map_check`), `page.no-goal`, `section.unrealized`, `section.unknown`,
`command.no-receiver`, `state.no-error`, `edge.carries-unset`; komponenta je uzel pod nejbližší stránkou v řetězu
`parentId`. Nová pole kontraktu se čtou jako nepovinná, nic se nedoplňuje.

## Cesty zákazníka (`journeys.py`)

Cesta zákazníka je trychtýř stránek (`site.journeys`, §3.2): proměnu zákazníka (`actor`, `pointA` → `pointB`) a kroky
s rolí, posunem `shift`, námitkou `objection`, signálem přechodu `via` a odbočkou `after` zadává člověk; počty lidí se
neukládají. `derive_journeys(graph)` (§6) odvodí každý přechod `after → krok` (segment): z menu nebo stránky po
hranách `carries ∈ {navigation, command, data}`, ze stránky do komponenty se sekcí a z komponenty zpět na její
stránku; nejkratší řada (BFS), remízy podle id. Vrací cestu s A → B a kroky (s `path`, u chybějící stránky
`missing`), `segments` `{from, to, line, realized}` a `line` kroků (`nav → /pestovani → /novinky`). Nerealizovaný
segment cestu nerozbije (`journey.unrealized` v kontrole mapy), `broken` má cesta jen s chybějící stránkou kroku
(`journey.broken`). Přesná pravidla jsou v docstringu modulu a v kontraktu §6. Čtení
`GET /api/project-architecture/journeys?project=` (router vedle kontroly mapy), u každé cesty s dokladem i `lastRun`.

## Brána cesty (`journey_plan.py`, `journey_runs.py`)

Dodatek `docs/brana-cesty.md`. `journey_plan(graph, journey_id, application_id=None)` je čistá funkce: z odvozené
cesty složí plán přehrání (`baseUrl`, segmenty `{from, to, open, scope, do, text?, expectPath}`, `digest`); čtení
`GET /api/project-architecture/journey-plan?project=&journey=&application=`. `journey_runs.py` ověří doklad
(`POST /api/project-architecture/journey-runs?project=`), odvodí `passed` a uloží ho append-only do tabulky
`journey_runs` v `project.sqlite`; `last_runs` z posledních dokladů a aktuálních digestů skládá `lastRun`
(`{at, passed, stale, command, failed, firstFailure?}`) pro `journeys`, `node-brief.architecture` a kontrolu mapy.
Opora cestu nepřehrává; runner je etapa 8c.

## Výřez mapy pro agenta (`node_architecture.py`)

`node_architecture(graph, nodeId)` skládá `node-brief.architecture` (§4) jen pro kartu pod stránkou: cesty, na kterých
leží stránka karty, jako řetěz „proč“: `actor` a A → B cesty, `youAre`, role `label`, posun `shift` a námitka
`objection` kroku a sousední kroky se signálem `via`; dál stránku a sekci karty, hrany s `carries`, stavy a díry
z kontroly mapy. Bez výchozích hodnot, strop 2,5 KiB s deterministickým ořezem po celých klíčích (`truncated`), který
před poslední záchranou nikdy nevezme A, B, posun, první `next` ani sekci. Volá ho `backend/editor/agent_packet/node_brief.py`.
