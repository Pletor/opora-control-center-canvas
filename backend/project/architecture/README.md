
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
`{findings: [{rule, nodeId|edgeId, message}], summary: {pravidlo: počet}}` nad přijatým grafem (architektura složená
s obsahem `main`, bez Gitu `draft`; čte ho `work_status.architecture_graph`). Bez modelu, deterministicky: pořadí
pravidel, pak id. Pravidla `page.no-goal`, `section.unrealized`, `command.no-receiver`, `state.no-error`,
`edge.carries-unset`; komponenta je uzel pod nejbližší stránkou v řetězu `parentId`. Nová pole kontraktu se čtou jako
nepovinná, nic se nedoplňuje. `journey.broken` přijde s cestami zákazníka (etapa 7).
