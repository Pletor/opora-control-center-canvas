
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

## Kontrola mapy přes worktree (`map_check_worktrees.py`)

Jediný zdroj děr mapy přes worktree (`docs/navrhy/2026-10-28-kontrola-mapy-a-worktree.md` §3).
`worktree_overlay(service, project)` vrací díry mainu a pro každý aktivní worktree `closed` (klíče děr mainu,
které worktree zalepil) a `opened` (nové díry worktree, max 50). Klíč je `map_check.finding_key`, tentýž jako
u dávky plánu. Nálezy worktree se drží v paměti procesu podle digestu pohledu. Čte ho
`GET /api/project-architecture/map-check/worktrees?project=` a `mapGaps` v agent-state.

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

Stav „cesta právě běží“ (§3a, `journey_running.py`): `JourneyRunning` drží běhy jen v paměti procesu (zámek, TTL
120 s od posledního heartbeatu, vstříknuté hodiny pro testy, strop 256 běhů). `start_journey_run` ověří cestu jako
plán a vrátí `{runId, startedAt}`; `progress` nese aktuální přechod; `project_journeys` přidá cestám `running`
a zápis dokladu běh té cesty smaže. Žádná SQLite, žádné schéma.

Brána uzavření (§5, `journey_gate.py`): `journeys_blocking(graph, nodeId, runs)` vrací cesty, které brání uzavření
karty (`{journeyId, applicationId, name, reason}`; „chybí ověření“ → „zastaralé“ → „neprošel přechod s2 → s3“ →
„nepokrývá všechny přechody“), `blocking_by_node` totéž pro více karet, `refusal` text odmítnutí. Karta leží na cestě,
když její nejbližší stránka (nebo ona sama) je stránkou kroku nerozbité cesty. Volá ji `backend/canvas/opora_card_done.py`
(požadavek `journeys` v definici hotovo, `closure_gate` i agent-state `cards[].dod`) a starší větev uzavření
v `backend/editor/agent_memory/desktop_v3_state.py`; graf je graf pracovního prostoru karty.

## Výřez mapy pro agenta (`node_architecture.py`)

`node_architecture(graph, nodeId)` skládá `node-brief.architecture` (§4) jen pro kartu pod stránkou: cesty, na kterých
leží stránka karty, jako řetěz „proč“: `actor` a A → B cesty, `youAre`, role `label`, posun `shift` a námitka
`objection` kroku a sousední kroky se signálem `via`; dál stránku a sekci karty, hrany s `carries`, stavy a díry
z kontroly mapy. Bez výchozích hodnot, strop 2,5 KiB s deterministickým ořezem po celých klíčích (`truncated`), který
před poslední záchranou nikdy nevezme A, B, posun, první `next` ani sekci. Volá ho `backend/editor/agent_packet/node_brief.py`.

Cíl z MODELu (`docs/studio.md` §4a) skládá `node_model_target.py`: `read_model_target(service, project, graph, nodeId)`
přečte model domény karty (aplikace karty, nikdy `scenario:*`) a vrátí `{source, domain, revision, type, name,
targets?, mustSurvive?, links?}` uzlu modelu navázaného na kartu, nebo None. `node_architecture(..., model=)` ho
vloží jako `architecture.model` (i u karty mimo stránku) a ořízne ho jako stupeň 0b hned po `holes`.
