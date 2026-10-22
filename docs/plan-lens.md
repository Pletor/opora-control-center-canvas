# Lens plánu

Plán z plátna jako graf PR Lens: oblasti, karty, předávky na vazbách a vazby v kódu, aby lidé
i agenti viděli, co je jen plán a co už v hlavní větvi stojí. Čte jen data, která už existují.
Je deterministický, takže stejné vstupy dají bajtově stejný spec, a **nikdy nevolá model**.
Diagram změny PR (PR Lens od pracovníka) popisuje [oporahub-review-jobs.md](oporahub-review-jobs.md#diagram-pr-lens-volitelný-důkaz);
Lens plánu je jeho protějšek pro celý plán bez PR.

## API

`GET /api/oporahub/plan-lens?project=&workspace=[&area=<id oblasti>]`

- **Identita** jako u `GET /api/oporahub/review-lens`: přihlášený člověk (cookie UI) nebo agent
  s `X-Opora-Actor: agent; name=…`, jinak **428** `identity_required`. Neplatný projekt nebo
  prostor dá 400, neznámá oblast (id, které není `kind: "area"`) **404** `area_not_found`.
- **Odpověď** `{kind: "plan", area: <id>|null, digest, spec, stats, graphify}`:
  - `digest` je sha256 kanonického JSON specu (setříděné klíče, bez mezer),
  - `spec` je graf PR Lens (`kind: "graph"`, `schemaVersion` 0.2.0), který projde
    `pr-lens validate` připnutého CLI (`tools/pr-lens`, schéma 0.7.x),
  - `stats` `{areas, cards, withCode, planned, standalone, unassigned}`: `cards` jsou karty
    v rozsahu pohledu (projekt = všechny uzly a sektory, oblast = jen její), `withCode` karty
    s kódem v main, `planned` ostatní, `standalone` karty bez jediné vazby plánu na jinou kartu,
    `unassigned` karty mimo všechny oblasti v celém grafu, `areas` počet oblastí (u oblasti 1),
  - `graphify` `{available, sourceRevision?}`: zda se našla mapa Graphify a z jaké revize je.
- **ETag** ze všech vstupů (digest grafu, revize stavu plochy, existující cesty, revize gitu,
  mapa Graphify a parametry dotazu); `If-None-Match` beze změny → **304** bez těla. Hotová
  odpověď se drží v `read_cache`, dokud se razítko nezmění.

## Pohled projektu (bez `area`)

- Každá oblast je uzel `module` s odznakem `x/y hotovo` (karty s `done.confirmed` / všechny
  karty oblasti). Stojí v pruhu nejčastější vrstvy svých karet; při remíze rozhoduje pořadí
  pruhů a prázdná oblast stojí v pruhu „Plán“.
- Tok mezi oblastmi (`port: "flow"`) je hrana `data`. Její popisek je první věta poslední zprávy
  na vazbě ze stavu plochy (`state.edges[id].handoff`, jinak `summary`), zkrácená na 80 znaků.
- Karty mimo všechny oblasti jsou jeden uzel „Nezařazeno · <pruh>“ za každý pruh, kde nějaké
  jsou. Uzel nese stejný odznak a v souhrnu názvy karet.

## Pohled oblasti (`area=<id>`)

- Uzly jsou karty (uzel i sektor) uvnitř oblasti. Členství počítá `backend/canvas/areas.py`
  `area_of`, takže jde o geometrii na stejné vrstvě plátna a karta vnořená v jiné kartě do oblasti
  rodiče nepatří.
- Pruh určuje `card.layer` (frontend, backend, database, library), jinak pruh „Plán“. Sousední
  oblasti jsou vpravo v pruhu „Sousední oblasti“.
- **Plán proti realitě:** karta se `sourceRef` původu `existing`, jejíž cesta (soubor nebo
  složka) v hlavním checkoutu existuje, je `unchanged` a nese `files: [{path}]` bez řádků.
  Ostatní karty (původ `planned`, bez cesty nebo s chybějící cestou) jsou `added` s odznakem
  „plán“. Plánovaná cesta se ukáže jen jako podtitulek. Uzavřená karta má odznak „hotovo“.
  Souhrn uzlu je první věta podstaty karty (nejvýš 200 znaků).
- **Vazby plánu:** `next` je hrana `call` (pořadí práce: „potom tahle karta“) a tlačítko bloku
  (`block`) je `dependency`. Ostatní porty (`action`, `rule`) jsou `other`. Hrana je `unchanged`,
  jen když jsou oba konce `unchanged`.
- **Sousedé:** vazba plánu z karty oblasti na kartu v jiné oblasti vede na vnější uzel té oblasti
  (`kind: external`). Tok `flow` z oblasti nebo do ní přidá souseda se zprávou toku v souhrnu.
  Tok spojuje oblasti, ne karty, a proto sám hranu nekreslí.
- **Vazby kódu** z mapy Graphify hlavního checkoutu (`graphify-out/graph.json`): vazby `imports`,
  `imports_from` a `calls` se převedou na dvojice souborů (`source_file` obou konců). Soubor patří
  kartě s nejkonkrétnější cestou zdroje, která ho pokrývá, a to napříč celým grafem. Vazba mezi
  kartami A a B vznikne, když soubor A odkazuje na soubor B a obě karty jsou v oblasti. Kreslí se
  jako `dependency` s `emphasis: "muted"` a popiskem „kód“.

## Limity a determinismus

- Uzly i hrany se řadí podle id. Nad limit PR Lens (256 uzlů, 512 hran) se ořízne konec a hrany
  na vynechané uzly zmizí. Souhrn i čip „Vynecháno“ řeknou, kolik uzlů a hran chybí.
- Id uzlů je `area:`, `card:`, `soused:` nebo `nezarazeno:` + id z plátna. Id, které nesplní vzor
  PR Lens nebo je delší než 128 znaků, se nahradí stabilním otiskem (`card:h<sha256>`).
- Prázdný rozsah dostane jediný uzel „Prázdný plán“, protože PR Lens vyžaduje aspoň jeden uzel.
- Dokument má tvar uložené mapy (`pr-lens export`): `id` `opora-plan:<projekt>/<prostor>[/<oblast>]`,
  `provenance` bez `pullRequest`, `base.sha == head.sha` (HEAD hlavního checkoutu, jinak
  `sourceRevision` Graphify, jinak `0000000` pro „žádný commit“), `repo` z remote `origin` na
  GitHubu, jinak `{owner: "opora", name: <projekt>}`, a `generator` `opora-plan-lens`. Nemá
  `generatedAt` ani walkthrough, protože čas by rozbil determinismus a mapa příběh změny nevypráví.

## Kód

`backend/canvas/plan_lens.py` (dokument, limity, statistiky), `plan_lens_views.py` (oba pohledy),
`plan_lens_cards.py` (karta jako uzel), `plan_lens_code.py` (vazby Graphify),
`plan_lens_source.py` (hlavní checkout jen ke čtení, cache a razítko),
router `backend/api/editor/opora_plan_lens_routes.py`. Testy leží vedle modulů. Jeden z nich
ověří vygenerovaný spec připnutým CLI a přeskočí se, když `tools/pr-lens` chybí.
