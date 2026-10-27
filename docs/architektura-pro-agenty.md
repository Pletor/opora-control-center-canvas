# Architektura pro agenty: mapa jako zadání, test a zpětná vazba

[Zpět na README](../README.md).

Stav: kontrakt schválený 2026-10-27, kód ho provádí po etapách (§9). Navazuje na
[pyramidu](pyramida.md), [kartu pro agenty](karta-pro-agenty.md), [architekturu projektu](architektura-projektu.md)
a [domény a worktree](domeny-a-worktree.md). Kde se s nimi liší, platí tento dokument a ty se upraví ve stejném PR,
které změnu provádí.

## 1. Proč

Mapa architektury domény je primárně **harness agentů**. Agent z ní ví, co stavět, kudy teče
zákazník i data a čím je hotovo; nemusí kvůli orientaci číst kód. Člověk z ní vidí celý obraz a píše jen
záměr. Každá **cesta zákazníka** je trychtýř stránek a proměna zákazníka z bodu A do bodu B (kudy zákazník
jde, jaký posun na každé stránce nastane, co ho brzdí a čím přejde dál) a je zároveň zadání i test: aplikace je pro člověka nerozbitná, když všechny přechody jejích cest
procházejí na skutečném kódu.

Smyčka: člověk napíše záměr → agent rozloží stránku (dávka `canvas-plan`) → kontrola mapy najde díry bez
modelu → člověk potvrdí dávku jedním rozhodnutím → agent staví s výřezem mapy v `node-brief` → harness ověří
cestu → výsledek se zapíše na mapu a do paměti role.

## 2. Kdo co píše (pyramida přes mapu)

| Úroveň | Prvek | Píše | Obsah |
|---|---|---|---|
| 0 Projekt | aplikace (`site.kind = "application"`) | člověk | prostředí, **cesty zákazníka** (`journeys`) |
| 1 Stránka | `site.kind = "page"` | člověk | `goal`, `feel`, `navLabel`; pořadí v menu dává pořadí uzlů (beze změny) |
| 2 Sekce | `site.sections` stránky | člověk ve formuláři stránky; agent smí navrhnout v dávce | role, název, záměr sekce |
| 3 Komponenta | uzel pod stránkou | agent | `card.section`, `card.tech`, `card.states`, `sourceRef`, kontroly |
| Vazby | hrany | agent | `carries` (druh toku) |
| Brána | cesta zákazníka (trychtýř) | stroj | výsledek ověření cesty |

Člověk pod úrovní sekcí nic nevyplňuje (pyramida §4). Formuláře pro člověka jsou jen na aplikaci a stránce;
sekce jsou součástí formuláře stránky, protože člověk určuje, co na stránce má být (rozhodnutí 2026-10-27).

## 3. Datový model (jen přidává)

Všechna nová pole jsou **nepovinná** a **nikdy se nedoplňují výchozí hodnotou**. Chybějící pole znamená
„neurčeno“. Důvod: záznamy OporaHubu (návrhy a změny grafu) jsou adresované obsahem a při čtení se znovu
odvozují; přidaný výchozí klíč by starý záznam zneplatnil a změnil digest každého pohledu.

### 3.1 Stránka (`site.kind = "page"`)

```json
{ "kind": "page", "path": "/kontakt",
  "goal": "Poptávka odeslaná do 2 minut",
  "feel": "klidně, důvěryhodně",
  "navLabel": "Kontakt",
  "sections": [
    { "id": "hero", "role": "hero", "name": "Hero", "intent": "Ozveme se do 24 h" },
    { "id": "form", "role": "cta", "name": "Formulář", "intent": "Jméno, e-mail, popis",
      "moves": "Rozptýlí obavu ze spamu: jen e-mail, ozveme se jednou do 24 h." } ] }
```

- `goal` 1–200 znaků, `feel` 1–120, `navLabel` 1–40. Prázdný řetězec se neukládá, pole se vynechá.
- `sections` 1–20 položek; `id` jako id uzlu, jedinečné ve stránce; `role` ∈ `hero | cta | form | content |
  gallery | proof | faq | footer | custom`; `name` 1–60; `intent` 0–200; nepovinné `moves` 1–120 (prázdné se
  neukládá): čím sekce posouvá zákazníka v kroku cesty, na kterém stránka leží (rozptýlí námitku, ukáže důkaz;
  [cesta-zakaznika-a-brief.md](cesta-zakaznika-a-brief.md) §2.3). Jiný klíč sekce validátor odmítne.
- Sekce navrhuje agent v dávce plánu (`site` stránky, i s `moves`) a skládá a upravuje člověk na dvou místech nad
  stejným dílkem: ve formuláři stránky na mapě domény a v záložce **Stránka** Detailu prvku v Editoru stránky.
- Sekce jsou součást `site` stránky, a tedy **zadání** (`specification`): změna sekce včetně `moves` mění
  `contextVersion` stránky a komponent pod ní (u karet mimo stránku ne).
- Proč v `site`, ne jako bloky: bloky žijí ve stavu pracovního prostoru (`state.nodes[id].blocks`), kdežto
  architektura je sdílená (`ARCHITECTURE_WID`). Sekce v `site` mají jednu pravdu, verzují se s revizí
  architektury, obnova revize je vrátí a smazání stránky nezanechá sirotky.

### 3.2 Aplikace (`site.kind = "application"`)

Cesta zákazníka je **trychtýř stránek** a zároveň **proměna zákazníka**: kdo je zákazník (`actor`), kde je na
začátku (`pointA`) a kým se stane (`pointB`). Každý krok je stránka (její id) s rolí v trychtýři, říká, jaký posun
na stránce nastane (`shift`) a co ho brzdí (`objection`), a nese ověřitelný signál přechodu `via`: co zákazník na
stránce předchozího kroku udělá, aby se dostal sem. Kroky jdou za sebou v pořadí seznamu; odbočka (`after`) naváže
krok na dřívější krok než ten předchozí. Cesta lidi nepočítá (zdůvodnění a rámce v
[cesta-zakaznika-a-brief.md](cesta-zakaznika-a-brief.md) §1–§3).

```json
{ "kind": "application", "environments": [{ "name": "Vývoj", "host": "localhost:3000" }],
  "journeys": [ { "id": "kurz", "name": "Prodej kurzu", "purpose": "Z návštěvníka platící zákazník s upsellem",
    "actor": "Začínající zahrádkář na balkoně",
    "pointA": "Rostliny mu hynou, neví proč, stydí se zeptat.",
    "pointB": "Má zelený balkon a ví, co dělá.",
    "steps": [
      { "id": "vstup", "page": "<id přistávací stránky>", "label": "Vstupní stránka", "via": { "do": "open" },
        "shift": "Z „nejde mi to“ na „asi je to naučitelné“." },
      { "id": "obsah", "page": "<id stránky s obsahem>", "label": "Obsah zdarma",
        "shift": "Zkusí první krok a funguje to.", "objection": "Zase spam.",
        "via": { "do": "click", "section": "hero", "text": "Chci video zdarma" } },
      { "id": "prodej", "page": "<id prodejní stránky>", "label": "Prodej",
        "via": { "do": "submit", "section": "form", "text": "Pošlete mi nabídku" } },
      { "id": "upsell", "page": "<id stránky upsellu>", "label": "Upsell", "via": { "do": "click" } },
      { "id": "mini", "page": "<id stránky miniupsellu>", "label": "Miniupsell", "after": "prodej" } ] } ] }
```

- `journeys` 1–20 položek (bez cest pole vynechte). Cesta `{id, name, purpose?, actor?, pointA?, pointB?, steps}`:
  `id` jako id uzlu, jedinečné v aplikaci; `name` 1–80; `purpose` 1–200 (obchodní cíl); `actor` 1–80 (pro koho
  agent píše a navrhuje); `pointA` 1–200 (situace, problém, pocit a překážky na začátku); `pointB` 1–200 (jeho
  „nové já“, dosažený pokrok); `steps` 2–30 kroků. A a B patří **cestě**, ne aplikaci: jedna aplikace má více
  zákazníků (rozhodnutí člověka, [cesta-zakaznika-a-brief.md](cesta-zakaznika-a-brief.md) „Rozhodnutí“).
- Krok `{id, page, label?, shift?, objection?, via?, after?}`: `id` jako id uzlu, jedinečné v cestě; `page` je id
  stránky aplikace, jen **první** krok smí mít `"nav"` (vstup z menu); `label` 1–60 (role kroku, např.
  „Vstupní stránka“, „Upsell“); `shift` 1–160 (jaký posun na stránce nastane, „z … na …“); `objection` 1–120
  (hlavní obava nebo zvyk, který posun brzdí); `after` = id **dřívějšího** kroku, na který tento navazuje
  (odbočka). Bez `after` krok navazuje na předchozí krok v seznamu; první krok `after` nemá. Cykly tak vzniknout
  nemohou. Emoce kroku se zvlášť neukládá (nese ji `site.feel` stránky).
- `via` = `{do, section?, text?}`: `do` ∈ `open | click | submit`; **první** krok smí mít jen `{"do": "open"}`
  (zákazník stránku otevře přímo), ostatní jen `click` (odkaz nebo tlačítko) a `submit` (formulář) **na stránce
  předchozího kroku** (`after`, jinak předchozí v seznamu). `section` je id sekce té stránky (tvar id uzlu),
  `text` 1–60 viditelný text nebo přístupné jméno prvku; obojí nepovinné. Doklad přechodu je URL stránky kroku
  (`site.path`), nepíše se. `via` je zadání (co má být klikatelné) i test pro harness etapy 8.
- `count` a `experience` (#101) se zrušily **bez migrace** a validátor je odmítne; `experience` nahradila dvojice
  `shift` + `objection`, `count` signál `via`.
- Prázdné texty se neukládají (klíč se vynechá), nic se nedoplňuje výchozí hodnotou. Zadává je člověk v mapě
  domény (panel „Cesty zákazníka“, editor trychtýře).
- Vazby mezi kroky (kudy zákazník po mapě opravdu jde) se **neukládají**, odvodí je stroj (§6). Přechod, který
  mapa vazbami nerealizuje, cestu nerozbije: je to práce pro agenty (`journey.unrealized`, §5).
- Uložení neověřuje, že stránka kroku existuje ani že `via.section` na předchozí stránce je: smazání stránky ani
  sekce nesmí zablokovat mapu. Krok s chybějící stránkou ohlásí kontrola mapy jako `journey.broken` a editor ukáže
  „chybí stránka“; signál se sekcí, kterou předchozí stránka nemá, jako `journey.via-unknown` a editor ukáže
  „chybí sekce“.
- Stará podoba `{id, name, from, to}` se už nepřijímá. Migrace není: v době změny ji živý backend ještě nenačetl,
  takže se nikde neuložila.
- Přidání ani úprava cesty (kroky, A → B, posun, námitka, `via`) nemění `contextVersion` karet (§4, `without_journeys`).
- `healthPath` zůstává beze změny (čte ho `web_status`).

### 3.3 Komponenta (uzel pod stránkou)

- `card.section`: id sekce (`site.sections[].id`) nejbližší stránky mezi předky karty (nejbližší předek se
  `site.kind = "page"` v řetězu `parentId`), kterou komponenta realizuje. Tvar id uzlu (`[A-Za-z0-9_-]{1,80}`),
  nepovinné, nikdy se nedoplňuje. Píše ho agent (dávka plánu: nová karta v `card`, existující v `extend` polem
  `section`, `null` smaže) a člověk v Detailu prvku (výběr „Sekce stránky“).
  - **Uložení grafu** (`validate_graph`) ověřuje jen tvar, ne existenci sekce: smazání sekce na stránce nesmí
    zablokovat uložení mapy (stejně jako cesty `site.journeys`, §3.2). Odkaz na chybějící sekci ohlásí kontrola
    mapy jako `section.unknown` a Detail prvku ho ukáže jako „chybí sekce …“.
  - **Dávka plánu** (agent) sekci, kterou zapisuje, ověří proti novému grafu a neexistující odmítne s důvodem;
    karta mimo stránku `card.section` mít nesmí.
- `card.tech`: 1–80 znaků, technologie realizace. `card.states`: 1–8 krátkých stavů
  (`prázdno`, `načítá`, `chyba`, `hotovo`…). Píše agent.

### 3.4 Hrana: `carries`

- Hodnoty `navigation | data | command | event`: navigace zákazníka, čtení dat, odeslání/zápis, událost.
- Název není `flow`: `flow` je už hodnota portu (tok mezi oblastmi, `backend/canvas/graph.py`).
- Smí ho mít hrana s portem `next` (i bez portu); hrana `flow`, `rule`, `action`, `block` ho mít nesmí.
- Port karty pro agenty (`next | action | rule | block`) se nemění. `carries` jen říká, co po vazbě teče.

### 3.5 Členství v oblasti

Zůstává **geometrické** (`areas.area_of`, `areaOf` na frontendu); `memberOf` beze změny. Změna sémantiky by
zneplatnila uložené záznamy změn grafu (odvozené `areaId`) a `contextVersion` rozpracovaných běhů.
Oblast při tahu karty roste (§8), ale nikdy nepřekryje cizí kartu ani oblast; kde by musela, karta se vysune ven
stejně jako dnes (`settleCard`).

## 4. Co dostane agent: `node-brief.architecture`

Nový klíč nejvyšší úrovně v `opora.node-brief/1`, **mimo `specification`**, takže nemění `contextVersion`.
Počítá ho backend deterministicky ze stejného grafu; nese jen větev karty. Strop asi 600 tokenů (2,5 KiB JSON).

```json
"architecture": {
  "journeys": [ { "id": "poptavka", "name": "Poptávka zahrady", "purpose": "Z návštěvníka poptávka s termínem prohlídky",
                  "actor": "Majitel rodinného domu se zanedbanou zahradou",
                  "pointA": "Zahrada ho tíží, nemá čas ani know-how, bojí se, že realizace bude drahá a nekonečná.",
                  "pointB": "Má jasný plán zahrady, pevnou cenu a termín; těší se ven místo výčitek.",
                  "youAre": { "step": "kontakt", "index": 2 }, "label": "Poptávka",
                  "shift": "Z „asi bych měl“ na „chci prohlídku, vím, co to stojí“.",
                  "objection": "Bojí se, že ho zavalíme telefonáty a skrytými cenami.",
                  "previous": { "step": "realizace", "label": "Ukázky realizací", "path": "/realizace", "realized": true,
                                "via": { "do": "click", "section": "cta", "text": "Chci podobnou zahradu" } },
                  "next": [ { "step": "dik", "label": "Potvrzení", "path": "/dekujeme", "realized": false,
                              "via": { "do": "submit", "section": "form", "text": "Odeslat poptávku" } } ],
                  "lastRun": { "passed": false, "stale": false } } ],
  "page": { "path": "/kontakt", "goal": "…", "feel": "…", "section": { "id": "form", "role": "form", "intent": "…", "moves": "…" } },
  "in":  [ { "carries": "navigation", "from": "Navbar" } ],
  "out": [ { "carries": "command", "to": "POST /api/poptavka", "sourceRef": "api/poptavka.py" } ],
  "states": ["prázdno", "odesílá", "chyba", "hotovo"],
  "gaps": ["state.no-error"]
}
```

Stránka je svou vlastní stránkou (i stránka přímo v menu dostane své cesty a posun svého kroku); karta, která není stránka ani neleží pod stránkou, klíč nedostane. `lastRun` cesty je `{passed, stale}` posledního
dokladu jejího přehrání (`docs/brana-cesty.md` §4), jen když cesta doklad má; ořez ho samostatně nebere.
Provádí `backend/project/architecture/node_architecture.py` (volá ho `node_brief.py`). Pravidla:

- **Bez výchozích hodnot.** Chybějící údaj = chybějící klíč; prázdný seznam (`journeys`, `in`, `out`, `gaps`)
  se vynechá, `states` jen když karta `card.states` má.
- **Řetěz „proč“.** `actor` a `pointA` → `pointB` cesty (proč cesta existuje) → `shift` a `objection` kroku (proč
  existuje stránka) → sousední kroky se signálem `via` (co se na stránce má stát) → `page.section.moves` (proč
  existuje sekce) → `node.purpose` v `brief.node`
  (proč existuje komponenta; tady se neopakuje). Agent tak ví, **co** staví (sekce + akce), **pro koho**, **proč**
  a **čím je hotovo** (přechod na stránku dalšího kroku).
- `journeys`: cesty zákazníka (§3.2), na kterých leží stránka karty (karta, která sama je stránka, jen ona; jinak
  nejbližší stránka). `youAre` = `{step, index}`: id a pořadí (od 0) prvního kroku s touto stránkou. `label`,
  `shift` a `objection` jsou role, posun a námitka kroku. `previous` je krok, na který tento navazuje (`after`,
  jinak předchozí), `next` kroky, které navazují na tento; soused = `{step, label?, path?, realized?, via?}`,
  `path` jen u existující stránky, `realized` (vede mezi kroky vazba na mapě, §6) jen u nerozbité cesty. `via`
  souseda je signál přechodu mezi ním a tímto krokem: u `previous` jak zákazník přišel sem (`via` tohoto kroku),
  u `next` co má zákazník udělat **na této stránce**, aby šel dál (`via` následujícího kroku) – pro komponentu
  nejdůležitější údaj. Rozbitá cesta (chybí stránka jiného kroku) roli kroku dál nese.
- `page`: `path`, `goal` a `feel` jen když jsou; `section` = `{id, role, intent, moves?}` jen když karta má
  `card.section` a nejbližší stránka sekci s tím id má; `moves` (čím sekce posouvá zákazníka) jen když ho sekce
  má. Stránka sama `section` nedostane.
- `in` / `out`: hrany karty s `carries`, v pořadí id hrany; `from` / `to` je název uzlu na druhé straně (bez
  názvu id), `sourceRef` jeho `sourceRef.path`, jen když je.
- `gaps`: pravidla kontroly mapy (§5), jejichž nález míří na kartu (`nodeId`) nebo na její hranu (`edgeId`);
  každé jednou, v pořadí pravidel.
- **Strop** 2560 B kompaktního JSON v UTF-8. Dokud výřez přesahuje, odebírá se po celých klíčích (texty se nikdy
  nezkracují, žádné „…“), každý stupeň jedna věc, a výřez dostane `"truncated": true`:
  1. cesty od konce, dokud nezbude jedna;
  2. hrany od konce, delší z `in` / `out` dřív (při shodě `out`);
  3. v první cestě `purpose`;
  4. v první cestě `next` od konce kromě prvního souseda, pak `previous.via`, pak celé `previous`;
  5. `page.feel`, pak `page.goal`;
  6. v první cestě `objection`;
  7. první cesta celá (poslední záchrana).

  `page.section` (i s `moves`) se neořízne nikdy; do sedmého stupně ani `actor`, `pointA`, `pointB`, `shift`
  a první `next`: to je řetěz „proč“. Test nejhoršího případu (texty na maximu limitů §3.2, dvoubajtová diakritika v A, B a posunu,
  8 stavů po 40 znacích) se vejde nejpozději po šestém stupni.
- **Verze zadání.** Cesty zákazníka nejsou zadání karty: `site.journeys` aplikace se do `specification` (graf
  `_node` i porovnání starých záznamů `scoped_specification`) nepromítá, takže přidání, změna ani smazání cesty
  `contextVersion` nemění (ani změna A → B, posunu, námitky nebo `via`). Ke kartě se cesta dostane jen tady.
  Naopak `moves` leží v `site.sections` stránky, tedy v zadání (§3.1): jeho změna `contextVersion` stránky
  a komponent pod ní mění záměrně (změnilo se zadání sekce).

## 5. Kontrola mapy

Čistá funkce bez modelu (nový modul `map_check` ve složce `backend/project/architecture/` s testem vedle). Spouští se nad
přijatou architekturou (čtení) a nad dávkou plánu i návrhem změny grafu (odmítnutí s důvodem). Výstup je seznam
`{rule, nodeId|edgeId|journeyId, message}`.

| Pravidlo | Kdy | Dopad |
|---|---|---|
| `journey.broken` | krok cesty míří na stránku, která chybí (smazaná nebo z jiné aplikace) | člověk opraví cestu |
| `journey.unrealized` | přechod mezi dvěma kroky cesty mapa vazbami nerealizuje (§6) | práce pro agenty |
| `journey.via-unknown` | signál přechodu kroku (`via.section`) míří na sekci, kterou stránka předchozího kroku nemá (menu sekce nemá nikdy) | práce pro člověka nebo agenta |
| `journey.unverified` | nerozbitá cesta bez `lastRun`, se zastaralým nebo neprošlým dokladem přehrání (`docs/brana-cesty.md` §4) | práce pro agenty |
| `section.unrealized` | sekce bez komponenty se `card.section` | práce pro rozkladače |
| `section.unknown` | karta odkazuje `card.section` na sekci, kterou nejbližší stránka nemá, nebo leží mimo stránku (`nodeId` karty) | práce (agent nebo člověk sekci opraví či zruší) |
| `command.no-receiver` | komponenta odesílá (`command`) a vazba nikam nevede | práce |
| `state.no-error` | komponenta s výstupem `command` nemá stav „chyba“ | práce |
| `edge.carries-unset` | hrana `next` mezi komponentami stránky bez `carries` | práce (migrace bez odhadu) |
| `page.no-goal` | stránka bez `goal` | jediná díra pro člověka |

Provádí `backend/project/architecture/map_check.py`; čtení nad přijatou architekturou je
`GET /api/project-architecture/map-check?project=`; výsledek je vidět na Mapě domény v panelu **Díry mapy** (nálezy domény po
pravidlech, klik otevře stránku, komponentu, zdroj hrany nebo editor cesty). `journey.broken` nese `journeyId` (id cesty v aplikaci) a zprávu
„Cesta <název>: chybí stránka <id> v kroku <role nebo id>.“; `journey.unrealized` jeden nález za každý
nerealizovaný přechod, `journeyId` a zprávu „Cesta <název>: z /a na /b nevede vazba (navigation, command, data ani
sekce stránky).“; `journey.via-unknown` jeden nález za každý takový krok, `journeyId` a zprávu „Cesta <název>: krok
<role nebo id> čeká akci v sekci <id>, kterou stránka /a nemá.“ (u menu „kterou menu nemá“); krok, jehož předchozí
stránka chybí, se nehodnotí (hlásí ho `journey.broken`). Nálezy cest jdou první (nejdřív `broken`, pak
`unrealized`, pak `via-unknown`; aplikace podle id, cesty v pořadí, v jakém je zadal člověk, přechody a kroky
v pořadí kroků). `journey.unverified` jde po nich: jeden nález za cestu, `journeyId` a zpráva „Cesta <název>: chybí
ověření …“, „… ověření je zastaralé …“ nebo „… neprošel přechod s2 → s3 (důvod).“; hodnotí ji jen čtení
`map-check` (doklady přehrání nejsou v grafu, dávka plánu ani návrh změny ji nehlásí).

Díry jsou práce pro agenty **jen v potvrzené dávce**; k člověku jde souhrn jako jedno rozhodnutí
(pyramida, pravidlo 4).

## 6. Cesta zákazníka

Člověk zadává kroky trychtýře (§3.2); stroj odvodí, kudy zákazník mezi nimi po mapě opravdu jde. Každý krok
kromě prvního tvoří s krokem, na který navazuje (`after`, jinak předchozí), **přechod (segment)**. Segment se
hledá z jeho začátku (menu nebo stránka) po hranách `carries ∈ {navigation, command, data}` a přes komponenty
se `card.section` až ke stránce cílového kroku. Nejkratší řada, deterministické pořadí podle id. Segment bez
souvislé řady cestu **nerozbije** (přechod člověk deklaroval, chybějící vazba je práce pro agenty,
`journey.unrealized`); rozbitá (`broken`) je cesta jen tehdy, když chybí stránka kroku.

Provádí `backend/project/architecture/journeys.py` (`derive_journeys`, čistá funkce bez modelu a I/O); čtení nad
přijatou architekturou je `GET /api/project-architecture/journeys?project=` →
`{journeys: [{applicationId, id, name, purpose?, actor?, pointA?, pointB?, steps, segments, line, lastRun?} | {applicationId, id, name, purpose?, actor?, pointA?, pointB?, steps, broken}]}`
(`lastRun` podle `docs/brana-cesty.md` §4).

- **Krok** ve výstupu: `{id, page, path?, missing?, label?, shift?, objection?, via?, after?}` (pole člověka beze
  změny). `path` je popisek stránky (`site.path`, menu = `nav`), u chybějící stránky místo něj `missing: true`.
  Konverze se nepočítá, cesta lidi neměří (§3.2).
- **Segment** `{from, to, line, realized}`: `from`/`to` jsou id kroků, `realized` říká, zda mapa přechod nese,
  `line` je jeho realizace (`/kontakt[form] → POST /api/poptavka → /dekujeme`), u nerealizovaného jen popisky
  obou kroků (`/obsah → /nabidka`).
- **`line` cesty** jsou popisky kroků v pořadí, v jakém je zadal člověk (`nav → /pestovani → /novinky → …`);
  podrobnosti přechodů jsou v `segments`. Rozbitá cesta nese jen `steps` a `broken` („chybí stránka X v kroku
  <role nebo id>.“).

Pravidla hledání segmentu:

- **Stránky aplikace** jsou stránky, jejichž nejbližší aplikace v řetězu `parentId` je tato aplikace. **Menu**
  (první krok s `page: "nav"`) jsou ty z nich, mezi kterými a aplikací neleží jiná stránka (jako `parentPageId == null`
  v `specification.navigation`). Menu je jen začátek: z menu se vstoupí na kteroukoli stránku v menu, zpět do
  menu se cesta nevrací. Stránka kroku, která sama je v menu, je z menu jedním krokem; stránka, na kterou se má
  dojít jen přes formulář (poděkování), patří pod jinou stránku jako podstránka.
- **Komponenta** je uzel pod stránkou (nejbližší stránka mezi předky, §3.3), který není stránka, aplikace,
  oblast ani komentář. **Komponenta se sekcí** má `card.section`, které nejbližší stránka má.
- **Kroky pohybu:** (1) hrana s `carries ∈ {navigation, command, data}` po směru `source → target` (`event` cestu
  nenese, oblasti a komentáře se neprocházejí); (2) stránka → její komponenta se sekcí (zákazník použije sekci);
  (3) komponenta → její stránka (výsledek, který dorazí do komponenty, vidí zákazník na její stránce).
- **Komponenta bez sekce:** ze stránky se do ní nevstupuje (nic neříká, kterou část stránky zákazník používá),
  po hraně (1) ji cesta projít smí. Důvod: API, databáze nebo služba pod stránkou sekci mít nemůže, a přesto
  leží na cestě; sekce je povinná jen pro vstup zákazníka ze stránky.
- **Nejkratší cesta** podle počtu kroků (BFS); startovní uzly i sousedé vzestupně podle id, každý uzel si
  pamatuje prvního předchůdce, takže remízu vyhraje cesta s menšími id dříve.
- **Popisky v `line` segmentu:** stránka = `site.path`, komponenta se sekcí = `/path[sectionId]` (cesta její
  stránky), ostatní uzly = název (bez názvu id), menu = `nav`. Stránka hned před vlastní komponentou se sekcí se
  slije do jejího popisku, stejně stránka hned po ní, pokud to není cíl segmentu.
Brána: karta, jejíž komponenta leží na cestě, se neuzavře, dokud poslední ověření cesty
neprošlo (etapa 8). Test cesty dodává výbava harnessu projektu (`harness.kit/1`, kategorie `testing`; u webu
typicky Playwright). Opora nástroj nepředepisuje, vyžaduje doklad. Plán přehrání (`GET
/api/project-architecture/journey-plan`), tvar dokladu (`POST /api/project-architecture/journey-runs`), `lastRun`
a bránu uzavření upřesňuje dodatek `docs/brana-cesty.md`. Brána je zapojená (etapa 8b): požadavek `journeys` v jediné
definici hotovo (`opora_card_done.py`) i ve starší větvi uzavření (`desktop_v3_state.py`); čistá funkce
`journey_gate.journeys_blocking` počítá `stale` nad grafem pracovního prostoru karty a odmítnutí (409) jmenuje cestu
a důvod. Agent-state ho ukazuje v `cards[].dod.journeys` a `dod.blockingJourneys`.

## 7. Co člověk vidí

Na doméně dva pohledy na stejná data: **Stránky** (karta stránky se sekcemi, cesty) a **Studio** (tok podle
`carries` a stav cest podle posledního ověření). Velín: jedna fronta „Čeká na tebe“. Monitor procesů se nestaví.

V Editoru stránky stojí nad plátnem pruh navigace domény (stejné stránky a popisky jako NAVBAR, aktivní stránka =
otevřený rozsah), úsek cesty zákazníka aktivní stránky (odkud → tato stránka s posunem a námitkou → kam, se signály
`via`; jen ke čtení, cesta se mění v trychtýři na mapě domény) a pruh sekcí s počtem komponent (`card.section`).
Podstránka je na plátně stránky odkazem na svou stránku, navigační vazby na ni zůstávají vidět
([návrh](cesta-zakaznika-a-brief.md) §5.1).

Trychtýř cesty na mapě domény i úsek cesty v Editoru stránky nesou odznak ověření z `lastRun`: „Ověřeno“,
„Ověření zastaralé“, „Neprošlo: s2 → s3 (důvod)“ nebo „Neověřeno“, s časem běhu (`domain-map/logic/journey-verification.ts`).
Detail karty má v definici hotovo dílek **Cesta ověřena** s blokujícími cestami v popisku.

## 8. Strom dopadů (co se musí upravit spolu)

Každá etapa upraví celý svůj strom v jednom PR, včetně testů, README dílků, skillu a dokumentů.

**Úklid karty (frontend):** `CardView` pole `doneProposed`, `openIdeas`, `briefChanged`, `cardModel`,
`cardEffort`, `cardStatus`, `design`, `round` (`frontend/editor/canvas/node-card/logic/card-model.ts`, `layer-nodes.ts`,
`card-model.test.ts`); `NodeCardData.usage` s řetězem `useUsage` → `Board` → `layer-nodes` (endpoint
`/usage-summary` zůstává, čte ho `node_brief.py`); duplicitní porty v `BriefTab.tsx`. Tóny `security`/`cache`
a `healthPath` **nejsou** mrtvé a zůstávají.

**Rostoucí oblast:** nová čistá funkce v `frontend/editor/canvas/area/logic/` (+ test) volaná z
`frontend/editor/canvas/board/components/Board.tsx` (tah) a `frontend/project/architecture-editor/page-editor/components/ArchitectureCanvas.tsx`
(`onNodeDragStop` dnes ukládá surovou pozici); zarážka o cizí kartu/oblast podle `solid-bodies.ts`; README
`area/` a `page-editor/`. `CENTRE_OFFSET` se nemění (musí sedět s backendem `areas._CENTRE_OFFSET`).

**Stránka a aplikace (`site`):** `backend/canvas/site_metadata.py` (+ `test_site_metadata.py`, trychtýř `journeys` §3.2);
`specification_context.py` `_navigation` (navigace v node-briefu, přidat `navLabel`); `frontend/shared/types/logic/types.ts` `NodeSite`;
`ArchitectureProductForm.tsx` (oprava: změna cesty dnes zahodí ostatní klíče `site`); `ArchitectureDomainMap.tsx`;
`PageCard.tsx`, `DomainPanel.tsx`; `product-tree.ts` `productFingerprint`; `frontend/project/architecture-editor/element-detail/logic/agent-context.ts`;
docs `architektura-projektu.md`, `domeny-a-worktree.md`; skill `.claude/skills/opora-control-center/references/api.md`.

**Hrana `carries` a komponenta `section`:** backend `graph.py` (`EDGE_KEY_SETS`, kontrola hodnot; klíč karty
`card.section`), `canvas_plan_links.py`, OporaHub `opora_graph_build.py`, `opora_graph_records.py`,
`opora_graph_change_records.py`, `opora_graph_change_plan.py`, `opora_graph_change_diff.py`, `node_brief.py`
`link()`, `canvas_index.py`, `trace.py`, `plan_lens_views.py`; frontend `types.ts` `GraphEdge`,
`board-model.ts`, `editor-model.ts`, `canvas-model.ts` `edgeLook`, `agent-context.ts`,
`frontend/hub/oporahub-overview/logic/overview.ts` (otisk grafu), `frontend/hub/graph-proposals/logic/graph-edits.ts`
(dnes natvrdo `port: "next"`), `GraphProposalDetails.tsx`, `GraphChangeReview.tsx`; testy podle hlášení
dopadů (grafové porty, plán, návrhy a změny grafu, node-brief, specifikace); docs `karta-pro-agenty.md`,
`oporahub-graph-proposals.md`; skill `.claude/skills/opora-control-center/references/canvas-plan.md`, `workflow.md`, `planner.md`, `rozklad.md`,
`.claude/skills/opora-control-center/assets/task-brief.md` (příklady ověřuje `.claude/skills/opora-control-center/scripts/test_skill_docs.py`). Změna `carries` na existující hraně
mění digest pohledu a zneplatní rozpracovaný výstup obou koncových karet; to je správně.

**`node-brief.architecture` (hotovo v etapě 7):** `node_brief.py` (+ `test_node_brief.py`), výřez
`backend/project/architecture/node_architecture.py` a cesty `journeys.py` (+ testy), `journey.broken`
a `journey.via-unknown` v `map_check.py`,
čtení `GET /api/project-architecture/journeys`, projekce zadání bez `site.journeys` (`assignment_scope.py`,
`specification_context.py`), skill `.claude/skills/opora-control-center/scripts/opora_read.py`
(souhrn) + `test_opora_read.py`, `references/api.md`, `karta-pro-agenty.md`; v mapě domény trychtýř cesty
(`CustomerJourneys.tsx`, `JourneyFunnel.tsx`, `JourneyFunnelEditor.tsx`, `JourneyStepCard.tsx`, `JourneyStepVia.tsx`,
logika `journeys.ts` a `journey-via.ts`) se signálem `via` a štítkem „chybí vazba“ u nerealizovaného přechodu
a role a posun stránky v cestách na kartě stránky (`PageJourneys.tsx`). Proměna A → B, posun, námitka a `via`
(2026-10-27, [cesta-zakaznika-a-brief.md](cesta-zakaznika-a-brief.md) PR 1–4) mění tytéž soubory a otisk
`productFingerprint` (`frontend/project/product-tree/logic/product-tree.ts`).

## 9. Etapy

| # | Etapa | Kontrakt mění |
|---|---|---|
| 1 | Úklid karty | ne |
| 2 | Oblast roste s kartou | ne |
| 3a | Stránka: `goal`, `feel`, `navLabel`, `sections` | `site` |
| 3b | Aplikace: `journeys` (od 2026-10-27 trychtýř stránek a proměna A → B se signálem `via`, §3.2) | `site` |
| 4 | Hrana `carries`, komponenta `section`: 4a `carries` (samostatně), 4b `section` (až po 3a) | graf, návrhy grafu |
| 5 | Komponenta `card.tech`, `card.states` | `card` |
| 6 | Kontrola mapy (§5) + API | ne |
| 7 | Cesty (§6) a `node-brief.architecture` (§4), hotovo | node-brief |
| 8 | Brána cesty: harness, doklad, `lastRun` | dodatek |
| 9 | Pohled Studio | ne |

Každá etapa je samostatný PR z čerstvého `origin/main` (`docs/cista-linie.md`). Před odevzdáním:
`uv run pytest backend`, `npm test`, `npm run build`, u skillu i jeho testy.

## 10. Co se nestaví

Monitor procesů, porty OS, spouštění skriptů, simulace zátěže, vlastní úložiště stránek a úkolů vedle grafu,
formuláře pro člověka pod úrovní sekcí, změna geometrického členství v oblasti.
