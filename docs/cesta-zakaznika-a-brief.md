# Cesta zákazníka jako proměna A → B a řetěz „proč“ v briefu agenta

[Zpět na README](../README.md) · navazuje na [architekturu pro agenty](architektura-pro-agenty.md) §3.2, §4, §6
a [kartu pro agenty](karta-pro-agenty.md).

Stav: **schváleno; PR 1–4 z §7 (cesta bez počtů, proměna A → B, posun a námitka, signál `via`) jsou v kódu
a kontraktu jedním PR** ([architektura-pro-agenty.md](architektura-pro-agenty.md) §3.2, §4, §5, §6). PR 5–6 (sekce
`moves`, Detail prvku, Editor stránky) čekají. Tvrzení o kódu v §1–§6 jsou ze stavu před implementací
(2026-10-27, `643e966`); živá data se nečetla.

## Rozhodnutí

Závazná rozhodnutí člověka k otázkám §8 (2026-10-27):

1. **Bod A/B (a aktér) žije na každé cestě** (`actor`, `pointA`, `pointB` v `site.journeys[]`), ne jednou na
   aplikaci. Aplikace bez cest A/B nemá.
2. **`experience` u kroku se nahrazuje dvojicí `shift` + `objection`, bez migrace.** Validátor `experience`
   i `count` odmítne (stejně jako dřívější podobu `{from, to}`).
3. **Sekce se upravují v Detailu Editoru stránky i ve formuláři stránky na mapě domény**, nad stejným dílkem
   `PageSectionsEditor` (PR 5–6, zatím ne).

Rozhodnutí při implementaci PR 1–4 (navíc k návrhu):

- První krok smí mít jen přesně `{"do": "open"}`: `section` ani `text` u otevření nemají předchozí stránku, ke které
  by patřily, a validátor je odmítne.
- `journey.via-unknown` hlásí i `via.section` u kroku za menu (`"nav"`): menu sekce nemá. Krok, jehož předchozí
  stránka chybí, se nehodnotí (to hlásí `journey.broken`).
- Ořez §4.3 má poslední záchranu (stupeň 7) dál; „nikdy“ platí do šestého stupně. Test nejhoršího případu
  (texty na maximu limitů, běžná id, 8 stavů po 40 znacích) se vejde bez sedmého stupně. S id a cestami stránek
  na jejich krajních délkách (80 / 2048 znaků) by se vejít nemusel.
- Při posunu kroku v editoru trychtýře signál, který k novému pořadí nesedí (klik u prvního kroku, otevření mimo
  začátek), zmizí; `via.section`, které nová předchozí stránka nemá, zůstane a ukáže se jako „chybí sekce …“.
- Textová pole cesty a kroku v editoru mění konec řádku na mezeru (backend řídicí znaky odmítne).

## 0. Shrnutí

- Cesta zákazníka zůstává trychtýřem stránek (`site.journeys` aplikace), ale **přestává měřit lidi** a začíná
  popisovat **proměnu**: kdo je zákazník (`actor`), kde je na začátku (`pointA`) a kým se stane (`pointB`).
- Každý krok (stránka na cestě) říká, **jaký posun** na stránce nastane (`shift`) a **co ho brzdí** (`objection`).
  `count` se ruší, `experience` nahrazuje dvojice `shift` + `objection`.
- Místo počtu lidí nese krok **ověřitelný signál přechodu** `via`: co zákazník na předchozí stránce udělá, aby se
  dostal sem (`click` / `submit` / `open`, v které sekci, na jakém prvku). Harness etapy 8 (Playwright) to umí
  zahrát a ověřit URL cílové stránky.
- Sekce stránky dostane jedno nové pole `moves`: čím sekce přispívá k posunu kroku.
- `node-brief.architecture` nese řetěz **A → B cesty → posun kroku → příspěvek sekce → úkol komponenty**
  (úkol = existující `node.purpose`), pod stropem 2,5 KiB s deterministickým ořezem.
- UI: v Editoru stránky přibude pruh navigace domény a **úsek cesty** aktivní stránky nad plátnem; rozbor
  sekcí (hero…) a jejich `moves` se dělá v Detailu prvku, když je vybraná stránka. Trychtýř na mapě domény
  ukazuje A nahoře, B dole a mezi kroky signál místo konverze.

## 1. Průzkum: jak se modeluje cesta a proměna zákazníka

Ze zdrojů beru jen to, co agentovi pomůže postavit stránku správně. Kde jsem primární text neověřil, je to
označené **[nejisté]**; citace jsou jen ty, které jsem na uvedené stránce opravdu viděl (v angličtině, krátce).

| Rámec | Co tvrdí (jádro) | Zdroj | Co si z toho bere OPORA |
|---|---|---|---|
| Jobs-to-be-Done (Christensen) | Job je „the progress they're trying to make as they strive toward a goal or aspiration within particular circumstances“; má funkční, sociální a emoční složku („functional, social, and emotional forces“). | [Christensen Institute: Jobs to Be Done][cci] · článek HBR [Know Your Customers' „Jobs to Be Done“][hbr] (Christensen, Hall, Dillon, Duncan; text za paywallem, definici jsem z něj neověřil **[nejisté]**) | Cesta je **pokrok v konkrétní situaci**, ne nákup. Bod A = okolnosti a snaha, bod B = dosažený pokrok. |
| Síly pokroku (Moesta, Spiek) | Ke změně dojde, jen když tlak situace („The push is the problem with the current situation“) a tah nového („the magnetism of the new way“) převáží úzkost z nového („Anxiety is the fear of the unknown“) a zvyk („the comfortable inertia of what people already know and do“). | [jobstobedone.org: The Four Forces][forces] | Krok má **posun** (tah) a **námitku** (úzkost / zvyk). Bez námitky agent staví jen „přidat výhody“; Moesta zdůrazňuje snižovat úzkost (záruka, zkušební verze…) – to je přesně to, co sekce mají dělat. Podrobnosti o vyvažování úzkosti jen ze sekundárních shrnutí **[nejisté]**. |
| Outcome-Driven Innovation (Ulwick) | Potřeby jsou „the metrics customers use to measure success when getting a job done“ (desired outcomes), na trhu jich bývá přes 100. | [Strategyn: Jobs-to-be-Done][strategyn] | Měřitelnost má smysl, ale OPORA neměří trh. Bereme z ní jen myšlenku **ověřitelného výsledku kroku** (`via`). Skladba výroku „směr + metrika + předmět“ je doložená jen sekundárně ([přehled ODI][odi2]) **[nejisté]**. |
| Value Proposition Canvas (Osterwalder, Strategyzer) | Profil zákazníka: „the jobs they are trying to get done“, „the pains they hit along the way“, „the gains they are after“; mapa hodnoty: co nabízíme, jaké bolesti tiší, jaké zisky tvoří. | [Strategyzer: The Value Proposition Canvas][vpc] | Bod A ≈ job + bolesti, bod B ≈ zisky. Sekce = **pain reliever / gain creator** konkrétního kroku → pole `moves`. |
| Customer journey mapping (NN/g) | Mapa má aktéra („The actor is who the journey map is about — a point of view“), scénář s očekáváním, fáze, v každé fázi akce, myšlení a emoce („Actions are the actual behaviors and steps taken by users“; „Mindsets correspond to users' thoughts, questions, motivations, and information needs“), a příležitosti. Jedna mapa = jeden pohled. | [NN/g: Journey Mapping 101][nng101] (Gibbons, 2018) · [NN/g: When and How to Create Customer Journey Maps][nngcjm] (Kaplan, 2016) | `actor` je na cestě (jedna cesta = jeden aktér). Fáze = kroky (stránky). **Akce** = `via`, **myšlení** = `objection`, **emoce** už nese `site.feel` stránky. |
| StoryBrand SB7 (Donald Miller) | Zákazník je hrdina, firma průvodce; sedm kroků: postava, problém (vnější, vnitřní, filozofický), průvodce, plán, výzva k akci, odvrácení selhání, úspěch. | Kniha *Building a StoryBrand* (2017); web [storybrand.com][sb] uvádí jen „The Customer is the Hero“. Sedm kroků a vrstvy problému jen ze [shrnutí knihy][sbnotes] **[nejisté]** | Bod A = problém (i vnitřní pocit), bod B = úspěch / nové já, stránka = plán a výzva k akci. Potvrzuje, že A i B patří do textu, který agent vidí na **každé** stránce. |
| Before–After–Bridge | Copy popíše stav „před“, žádoucí stav „po“ a nabídku jako most mezi nimi. | Jen praktické zdroje, např. [Campaign Monitor: BAB][bab]; původ vzorce se mi doložit nepodařilo **[nejisté]** | Přesně tvar `pointA` → `pointB`, most = cesta stránek. |
| Úrovně povědomí (Eugene Schwartz, *Breakthrough Advertising*) | Trh je na různé úrovni povědomí: neví o problému → zná problém → zná řešení → zná produkt → plně informovaný; text musí začít tam, kde čtenář je. | Kniha (1966, rok jen ze sekundárních zdrojů) mi nebyla dostupná; pět úrovní jen ze [shrnutí][schwartz] **[nejisté]** | Neukládáme jako pole (bylo by šesté pole kroku a agent ho odvodí z pořadí kroku a `shift`). Hodí se jako **nápověda v placeholderu** posunu („z „nevím, že to jde“ na „vím, že to jde a kdo to umí““). |

Závěr pro návrh: všechny rámce se shodnou na čtyřech věcech, které agent potřebuje a dnes je nemá:
**kdo** (aktér), **odkud kam** (A → B), **co se změní na této stránce** (posun) a **co tomu brání** (námitka /
úzkost). Měření počtů lidí (trychtýř s konverzemi) je nástroj analytiky, ne zadání stavby – a OPORA ho nemá
čím naplnit (§3).

## 2. Minimální sada polí

Pravidla zůstávají z kontraktu §3: vše nepovinné, prázdný text se neukládá, nic se nedoplňuje výchozí hodnotou,
krátký text bez řídicích znaků (`_text` v `site_metadata.py`). Test „méně je víc“: u každého pole je napsané,
**co agent postaví špatně, když chybí**.

### 2.1 Cesta (na úrovni aplikace, `site.journeys[]`)

A a B patří k **cestě**, ne k aplikaci: jedna aplikace má více cest a více aktérů (kupec kurzu, firemní
zákazník); NN/g výslovně „jedna mapa = jeden pohled“. Cesty leží v `site` aplikace, takže jde pořád o úroveň
aplikace, kterou píše člověk.

| Pole | Píše | Limit | Proč ho agent potřebuje (co bez něj postaví špatně) | Jak se ověří |
|---|---|---|---|---|
| `name` (už je) | člověk | 1–80 | – | validátor |
| `purpose` (už je) | člověk | 1–200 | Obchodní cíl („z návštěvníka poptávka“); bez něj neví, co je na konci úspěch pro nás. | validátor |
| `actor` **nové** | člověk | 1–80 | Pro koho píše a navrhuje: tón, slovník, příklady, bariéry přístupnosti. Bez něj píše pro „uživatele obecně“. | validátor; kontrola mapy nic |
| `pointA` **nové** | člověk | 1–200 | Situace, problém, pocit a překážky zákazníka na začátku. Bez něj hero mluví o nás, ne o jeho problému (StoryBrand, JTBD push). | validátor |
| `pointB` **nové** | člověk | 1–200 | Jeho „nové já“ / dosažený pokrok. Bez něj agent neví, k čemu každá stránka směřuje, a staví výčet funkcí. | validátor |

### 2.2 Krok (stránka na cestě, `steps[]`)

| Pole | Píše | Limit | Proč ho agent potřebuje | Jak se ověří |
|---|---|---|---|---|
| `id`, `page`, `after`, `label` (už jsou) | člověk | beze změny | Pořadí, stránka, odbočka, role kroku. | validátor, `journey.broken` |
| `shift` **nové** (nahrazuje `experience`) | člověk | 1–160 | Jaký posun na této stránce nastane („z „asi bych měl“ na „chci prohlídku““). Bez něj agent neví, co je úkol stránky v proměně, a všechny stránky dělají totéž. | validátor |
| `objection` **nové** (nahrazuje `experience`) | člověk | 1–120 | Hlavní obava / zvyk, který posun brzdí (JTBD anxiety + habit, NN/g mindset). Bez něj agent nepostaví záruku, FAQ, mikrocopy u formuláře. | validátor |
| `via` **nové** (nahrazuje `count`) | člověk (agent smí navrhnout v dávce) | viz §3 | Jak se zákazník do tohoto kroku dostane z předchozího. Bez něj agent neví, které tlačítko / formulář je přechod, a harness nemá co testovat. | validátor tvaru; `journey.via-unknown` v kontrole mapy; etapa 8 přehráním |
| `count` | – | **ruší se** | §3 | – |
| `experience` | – | **ruší se** | Míchá emoce (to už nese `site.feel` stránky) a posun; rozdělí se na `shift` a `objection`. | – |

Emoce kroku se zvlášť neukládá: emoční tón stránky je `site.feel` (už existuje, je v zadání stránky). Úroveň
povědomí (Schwartz) se neukládá: vyplývá z pořadí kroku a z `shift`.

### 2.3 Sekce (`site.sections[]` stránky)

| Pole | Píše | Limit | Proč ho agent potřebuje | Jak se ověří |
|---|---|---|---|---|
| `id`, `role`, `name`, `intent` (už jsou) | člověk, agent navrhuje v dávce | beze změny | Co sekce obsahuje. | validátor |
| `moves` **nové** | člověk (agent smí navrhnout v dávce) | 0–120 | Čím sekce přispívá k posunu kroku: „rozptýlí obavu ze spamu“, „ukáže, že to zvládl někdo jako on“. Bez něj agent postaví formulář, ale ne důvod, proč ho zákazník vyplní. | validátor |

Pozor: dnes validátor sekce vyžaduje **přesně** `{id, role, name, intent}` (`set(section) != SECTION_KEYS`,
`site_metadata.py`); `moves` musí být volitelný klíč. Sekce jsou součástí `site` stránky, a ta **je** v zadání
karet (`specification`), takže změna `moves` mění `contextVersion` komponent pod stránkou. To je správně: sekce
je zadání (§2 kontraktu: člověk určuje, co na stránce má být).

### 2.4 Komponenta

Žádné nové pole. Úkol komponenty je existující `node.purpose` (píše agent v dávce) a sekce `card.section`.
Řetěz „proč“ se k ní dostane přes brief (§4).

## 3. Náhrada za `count`: signál kroku `via`

### 3.1 Tvar

```json
{ "id": "dik", "page": "<id /dekujeme>", "label": "Potvrzení",
  "shift": "Ví, že se mu ozveme do 24 h a co bude dál.",
  "via": { "do": "submit", "section": "form", "text": "Odeslat poptávku" } }
```

- `via.do` ∈ `open | click | submit`:
  - `open` – zákazník stránku otevře přímo (jen první krok, typicky `page: "nav"` nebo vstup z reklamy);
  - `click` – klikne na odkaz / tlačítko na stránce předchozího kroku;
  - `submit` – odešle formulář na stránce předchozího kroku.
- `via.section` – id sekce **stránky předchozího kroku** (`after`, jinak předchozí v seznamu), ve které akce
  proběhne. Tvar id uzlu; nepovinné.
- `via.text` – 1–60 znaků, viditelný text / přístupné jméno prvku („Odeslat poptávku“). Nepovinné.
- První krok smí mít jen `do: "open"`; ostatní jen `click | submit`.
- Doklad přechodu je vždy **URL cílové stránky kroku** (`site.path` stránky kroku); nepíše se, odvodí se.

### 3.2 Co s tím udělá harness (etapa 8)

Pro přechod `předchozí → tento krok` umí Playwright: otevřít `host + path předchozí stránky` (host z
`environments` aplikace), najít sekci (navrhuji konvenci atributu `data-opora-section="<id>"`, konvenci určí
dodatek etapy 8 **[nejisté]**), v ní prvek podle role a jména (`getByRole('button'|'link', { name: via.text })`),
kliknout / odeslat (data formuláře dodá výbava harnessu, ne mapa) a ověřit, že URL odpovídá `path` tohoto kroku.
Výsledek se zapíše do `lastRun` (kontrakt §4, etapa 8). `via` bez `section` / `text` je pořád testovatelný:
harness hledá jakýkoli odkaz na cílovou cestu.

Proč ne počet lidí: OPORA nemá analytiku ani přístup k návštěvnosti; číslo by zadal člověk odhadem, agent ho
nemá jak využít ke stavbě a nikdo ho neověří. `via` je naopak **zadání** (co má být klikatelné) i **test**.

### 3.3 Kontrola mapy

- `journey.via-unknown` (nové, práce pro člověka nebo agenta): `via.section` míří na sekci, kterou stránka
  předchozího kroku nemá; `journeyId` + zpráva „Cesta X: krok Y čeká akci v sekci Z, kterou stránka /a nemá.“
- Volitelné zpřesnění odvození segmentů (`journeys.py`): když `via.section` existuje, segment začne od komponent
  té sekce místo od celé stránky. Nemění tvar výstupu, jen přesnost `realized`. Do prvního PR nepatří.

### 3.4 Co s existujícími cestami s `count`

Ověřeno jen z kódu: `count` a `experience` přidalo PR #101 (`643e966`, dnešní HEAD); předchozí podoba z #98
(`{id, name, from, to}`) `count` neměla a validátor ji už odmítá. Kontrakt §3.2 sám uvádí, že živý backend tvar
cest ještě nenačetl. Návrh:

- **Vypustit bez migrace**, stejně jako při přechodu z `{from, to}`: `STEP_OPTIONAL_KEYS` přestane znát
  `count` a `experience`, odvození přestane počítat `rate`, frontend přestane číst/psát `count`.
- Pojistka pro ruční data: autor PR před sloučením ověří (člověk, ne agent), že v datovém kořeni žádná cesta
  `count`/`experience` nemá; kdyby měla, uložení grafu by selhalo. V tom případě jednorázově `experience` →
  `shift` (oříznout na 160) a `count` zahodit, v témže PR.
- Testy: `test_journeys.py` (trychtýř s počty a `rate`), `test_node_architecture.py`, `test_site_metadata.py`,
  `journeys.test.ts` se přepíšou na `shift` / `via`.

## 4. `node-brief.architecture`: řetěz „proč“

### 4.1 Tvar (komponenta hluboko pod stránkou)

Řetěz: `journeys[].pointA → pointB` (proč existuje cesta) → `shift` / `objection` kroku (proč existuje stránka)
→ `page.section.moves` (proč existuje sekce) → `node.purpose` v `brief.node` (proč existuje komponenta; neopakuje
se tu). Pro kartu, která je sama stránkou, `page.section` chybí. Komponenta v podsektoru pod stránkou dostane
stejný výřez jako přímé dítě stránky (nejbližší stránka přes `nearest_page`, beze změny).

```json
"architecture": {
  "journeys": [ {
    "id": "poptavka", "name": "Poptávka zahrady", "purpose": "Z návštěvníka poptávka s termínem prohlídky",
    "actor": "Majitel rodinného domu se zanedbanou zahradou",
    "pointA": "Zahrada ho tíží, nemá čas ani know-how, bojí se, že realizace bude drahá a nekonečná.",
    "pointB": "Má jasný plán zahrady, pevnou cenu a termín; těší se ven místo výčitek.",
    "youAre": { "step": "kontakt", "index": 2 }, "label": "Poptávka",
    "shift": "Z „asi bych měl“ na „chci prohlídku, vím, co to stojí“.",
    "objection": "Bojí se, že ho zavalíme telefonáty a skrytými cenami.",
    "previous": { "step": "realizace", "label": "Ukázky realizací", "path": "/realizace", "realized": true,
                  "via": { "do": "click", "section": "cta", "text": "Chci podobnou zahradu" } },
    "next": [ { "step": "dik", "label": "Potvrzení", "path": "/dekujeme", "realized": false,
                "via": { "do": "submit", "section": "form", "text": "Odeslat poptávku" } } ] } ],
  "page": { "path": "/kontakt", "goal": "Poptávka odeslaná do 2 minut", "feel": "klidně, důvěryhodně",
            "section": { "id": "form", "role": "form", "intent": "Jméno, e-mail, popis zahrady",
                         "moves": "Rozptýlí obavu ze spamu: jen e-mail, ozveme se jednou do 24 h." } },
  "in":  [ { "carries": "navigation", "from": "Navbar" } ],
  "out": [ { "carries": "command", "to": "POST /api/poptavka", "sourceRef": "api/poptavka.py" } ],
  "states": ["prázdno", "odesílá", "chyba", "hotovo"],
  "gaps": ["journey.unrealized"]
}
```

`previous.via` = jak zákazník přišel sem (akce na předchozí stránce); `next[].via` = co má zákazník udělat **na této
stránce**, aby šel dál – to je pro komponentu nejdůležitější údaj (formulář s tlačítkem „Odeslat poptávku“ v sekci
`form` je přesně ta komponenta). Agent tak ví, **co** staví (sekce + akce), **pro koho** (`actor`), **proč**
(A → B, posun, námitka, `moves`) a **čím je hotovo** (přechod na `/dekujeme`, `lastRun`).

### 4.2 Velikost

Změřeno na kompaktním JSON v UTF-8:

| Případ | Bajty |
|---|---|
| Příklad výše (jedna cesta, realistické texty) | 1 386 B |
| Jedna cesta, všechna pole na maximu limitů §2 (pesimisticky dvoubajtová diakritika v A/B/posunu) | 2 446 B |
| `page` na maximu (goal 200, feel 120, sekce s intent 200 a moves 120) | 792 B |

Typická karta se vejde s rezervou; nejhorší případ jedné cesty + stránky (~3,2 KiB) strop 2 560 B přetéká, proto
se mění pořadí ořezu.

### 4.3 Deterministický ořez (náhrada `_fit` v `node_architecture.py`)

Dokud výřez přesahuje 2 560 B, odebírej v tomto pořadí, každý krok celý, a nastav `"truncated": true`:

1. cesty od konce, dokud nezbude jedna (beze změny);
2. hrany: delší z `in` / `out` od konce, při shodě `out` (beze změny);
3. v první cestě `purpose` (obchodní cíl; agenta vede hlavně A → B);
4. v první cestě `next` od konce **kromě prvního** souseda, pak `previous.via`, pak celé `previous`;
5. `page.feel`, pak `page.goal`;
6. v první cestě `objection`;
7. první cesta celá (beze změny, poslední záchrana).

Nikdy se neořezávají `pointA`, `pointB`, `shift`, první `next` ani `page.section`: to je řetěz „proč“. Texty se
nezkracují uprostřed (žádné „…“); ořez je čistě po klíčích, takže je deterministický a testovatelný.

### 4.4 Verze zadání

- `actor`, `pointA`, `pointB`, `shift`, `objection`, `via` leží v `site.journeys` aplikace → **mimo
  `specification`** (`without_journeys` v `assignment_scope.py` je odstraní celé), `contextVersion` se jejich
  změnou nemění. Ke kartě se dostanou jen přes `architecture`.
- `moves` leží v `site.sections` stránky → **v `specification`** jako dnes `intent`; jeho změna `contextVersion`
  komponent pod stránkou mění (správně: změnilo se zadání sekce).

## 5. UI

Zásady: jedno rozhraní pro všechny projekty (žádné větvení podle `sourceKind`), dílky dostávají hotová data a hlásí
změny nahoru, ukládá jen `ArchitectureEditor` přes existující `saveProduct` (cesty) a `saveGraph` (sekce stránky).
Úpravy cest a sekcí jsou **struktura** (`structureLock`, zapisovatelné i na mainu), stejně jako dnes formulář
stránky a trychtýř.

### 5.1 Aktivace stránky a plátno Editoru stránky

Dnes: tlačítko v NAVBARU mapy domény i položka stromu (`ProjectTree` → `onOpenPage`) otevřou Editor stránky
(`scopeId`), plátno ukáže jen komponenty. Navrhuji:

- **Aktivní stránka = otevřený rozsah** (`scopeId`, už v URL `pageId`). Žádný druhý stav „aktivní“.
- V hlavičce plátna Editoru stránky přibude **pruh navigace domény** (stejné položky jako NAVBAR mapy domény,
  `navLabelOf`); aktivní stránka je zvýrazněná, klik přepne rozsah (`onOpenPage`). Podstránka zvýrazní svého
  předka v pruhu a ukáže se v drobečcích.
- Mezi hlavičkou a plátnem je **úsek cesty**: pro každou cestu, na které stránka leží, jeden řádek
  „odkud → TATO STRÁNKA → kam“. Data: `site.journeys` aplikace + odvozené segmenty (`useDerivedJourneys` už
  v `ArchitectureEditor` běží). Řádek je ve výchozím stavu sbalený na jednu linku; rozbalený ukazuje A/B cesty,
  posun, námitku a signály. **Upravit krok** otevře na místě stejné pole jako karta kroku v trychtýři
  (`shift`, `objection`, `via` příchozího přechodu) a uloží celé `site` aplikace s otiskem.
- Sekce na plátně: pod úsekem cesty pruh štítků sekcí stránky (role · název) s počtem komponent, které je
  realizují (`card.section`), a varováním u sekce bez komponenty (`section.unrealized` z kontroly mapy). Klik na
  štítek vybere stránku v Detailu a rozbalí tu sekci.

```
┌ Editor stránky ─────────────────────────────────────────────────────────────────────────────┐
│ Strom / Knihovna │ Mapa architektury — Kontakt                                 [web ●]     │
│                  │ NAVBAR  Úvod   Realizace   [Kontakt]   Ceník   Blog                     │
│ ▾ Úvod           │ ┌ Úsek cesty ─────────────────────────────────────────────── ▾ ┐       │
│ ▾ Realizace      │ │ Poptávka zahrady · krok 3/4 „Poptávka“                         │       │
│ ▸ Kontakt  ◀     │ │ /realizace ──klik „Chci podobnou zahradu“ (cta)──▶ [ /kontakt ] │       │
│   ↳ Děkujeme     │ │            ──odešle „Odeslat poptávku“ (form)──▶ /dekujeme ⚠ chybí vazba│
│                  │ │ Posun: z „asi bych měl“ na „chci prohlídku, vím, co to stojí“   │       │
│                  │ │ Námitka: bojí se telefonátů a skrytých cen        [Upravit krok]│       │
│                  │ └──────────────────────────────────────────────────────────────────┘       │
│                  │ Sekce: [Hero ·2] [Důvěra ·1] [Formulář ·1] [FAQ ⚠ 0]                   │
│                  │ ┌ plátno React Flow (oblasti, sektory, uzly) ───────────────────────┐ │
│                  │ │   …                                                              │ │
└──────────────────┴─┴──────────────────────────────────────────────────────────────────┴─┘
```

Stránka, která na žádné cestě neleží: úsek cesty ukáže jednu tichou větu „Stránka není na žádné cestě
zákazníka – přidejte ji v trychtýři na mapě domény“ s odkazem; nic jiného.

### 5.2 Rozbor stránky v Detailu prvku

Když je vybraná sama stránka (po otevření rozsahu se vybere automaticky, `navigate` nastaví `selectedId`),
Detail prvku dostane záložku **Stránka** (vedle Zadání / Vazby / Práce): cíl, působení, popisek v menu a
**sekce** s rolí, názvem, záměrem a novým polem „Čím posouvá“ (`moves`). Nahoře připomínka, k jakému posunu
stránka slouží (`shift` z cest, jen ke čtení). Editor sekcí je existující `PageSectionsEditor` (přesune se do
sdíleného místa, mapa domény ho používá dál ve formuláři stránky).

```
┌ Detail prvku: Kontakt ───────────────┐
│ [Stránka] Zadání  Vazby  Práce        │
│ Na cestě: Poptávka zahrady · Poptávka │
│ Posun: z „asi bych měl“ na „chci …“   │
│ Námitka: telefonáty, skryté ceny      │
│ Cíl  [Poptávka odeslaná do 2 minut ]  │
│ Působení [klidně, důvěryhodně      ]  │
│ Sekce                                 │
│ ┌ Hero ▾ │ Hero                     ┐ │
│ │ Záměr  [Ozveme se do 24 h        ]│ │
│ │ Posouvá[Ukáže, že rozumíme jeho…  ]│ │
│ │ komponenty: HeroBanner, Fotka   ↑↓│ │
│ └───────────────────────────────────┘ │
│ ┌ Formulář ▾ │ Formulář … (2 komp.) ┐ │
│ + Přidat sekci        [Uložit stránku]│
└───────────────────────────────────────┘
```

Komponenta (ne stránka) v Detailu dál vybírá sekci (`SectionPicker`); pod výběrem se nově ukáže jedna řádka
řetězu „proč“: `A → B · posun kroku · sekce posouvá …`, aby člověk viděl totéž, co dostane agent.

### 5.3 Trychtýř bez čísel (mapa domény)

`JourneyFunnel` / `JourneyFunnelEditor` zůstávají jediným místem, kde se cesta zakládá, řadí a maže. Změny:
nahoře aktér a bod A, dole bod B; krok ukazuje roli · stránku · posun (a námitku menším písmem); šipka mezi kroky
místo konverze nese signál (`klik „…“ v sekci cta`) a dál štítek „chybí vazba“ / po etapě 8 výsledek posledního
ověření. Pole „Počet lidí“ v kartě kroku mizí, „Co člověk zažívá…“ se rozdělí na Posun a Námitku, přibude
„Jak sem přijde“ (akce, sekce předchozí stránky – výběr ze `site.sections`, text tlačítka).

```
┌ Prodej kurzu ─────────────────────────────────────────── [Upravit] ┐
│ Pro: začínající zahrádkář na balkoně                                │
│ A ▸ Rostliny mu hynou, neví proč, stydí se zeptat.                  │
│   ┌ Vstupní stránka · Menu ─────────────────────────────┐           │
│   │ Posun: z „nejde mi to“ na „asi je to naučitelné“    │           │
│   └──────────────────────────────────────────────────────┘           │
│        ↓ klik „Chci video zdarma“ (hero)                             │
│   ┌ Obsah zdarma · /video ──────────────────────────────┐           │
│   │ Posun: zkusí první krok a funguje to                 │           │
│   │ Námitka: „zase spam“                                 │           │
│   └──────────────────────────────────────────────────────┘           │
│        ↓ odešle „Koupit kurz“ (form)        chybí vazba              │
│   ┌ Prodej · /kurz … ┐                                               │
│ B ▸ Má zelený balkon a ví, co dělá.                                 │
└─────────────────────────────────────────────────────────────────────┘
```

NAVBAR mapy domény se nemění (klik otevře Editor stránky = aktivuje stránku). `PageJourneys` na kartě stránky
přidá k roli posun („Prodej kurzu · Upsell (krok 4) – z … na …“), jen první řádek.

### 5.4 Dotčené existující soubory

| Oblast | Soubory |
|---|---|
| Kontrakt | `docs/architektura-pro-agenty.md` §3.1–§3.2, §4, §5, §6, `docs/karta-pro-agenty.md` (architecture), `.claude/skills/opora-control-center/references/api.md` |
| Validátor | `backend/canvas/site_metadata.py` (+ `test_site_metadata.py`): `JOURNEY_OPTIONAL_KEYS`, `STEP_OPTIONAL_KEYS`, `STEP_TEXT_LIMITS`, `via`, `SECTION_KEYS` → volitelné `moves` |
| Odvození | `backend/project/architecture/journeys.py` (`rate` pryč, nové klíče do kroků), `map_check.py` (`journey.via-unknown`), `node_architecture.py` (`_journeys`, `_neighbour`, `_page`, `_fit`) + jejich testy |
| Skill | `.claude/skills/opora-control-center/scripts/opora_read.py` + `test_opora_read.py` (souhrn cest) |
| Typy | `frontend/shared/types/logic/types.ts` (`JourneyStep`, `CustomerJourney`, `PageSection`) |
| Mapa domény | `domain-map/logic/journeys.ts` (+test), `page-site.ts` (+test), `page-journeys.ts` (+test), `derived-journeys.ts` (+test), `JourneyFunnel.tsx`, `JourneyFunnelEditor.tsx`, `JourneyFunnelLink.tsx`, `JourneyStepCard.tsx`, `PageSectionsEditor.tsx`, `PageJourneys.tsx`, `CustomerJourneys.tsx` (prázdný text), `styles/domain-map.css`, `README.md` |
| Editor stránky | `components/ArchitectureEditor.tsx` (předá cesty, derivované segmenty a `onSaveJourneys` / `onSavePage`), `page-editor/components/PageEditor.tsx` (sloty pruhu a úseku), nový dílek `page-editor/journey-slice/` (`components/`, `logic/page-slice.ts` + test, `styles/journey-slice.css`, README), `page-editor/README.md` |
| Detail prvku | `element-detail/components/ElementDetail.tsx` (záložka Stránka), nový dílek `element-detail/page-tab/` (nebo komponenta `PageTab.tsx` s logikou v `logic/`), `logic/agent-context.ts` (+test, řádka řetězu), `SectionPicker.tsx` |

## 6. Ověření (pro každý PR)

`uv run pytest` cíleně (`backend/canvas/test_site_metadata.py`, `backend/project/architecture/`,
`backend/editor/agent_packet/test_node_brief.py`, `test_assignment_scope.py`, skill `test_opora_read.py`), `npm test`,
`npm run build`; celá backend sada jen před posledním PR série (paměť: 34 min).

## 7. Rozpad na malé PR

Každý z čerstvého `origin/main`, bez řetězení větví. PR 1–4 sahají na stejné soubory validátoru a trychtýře,
proto se nakonec **sloučily do jednoho PR** (2026-10-27, ✅ v tabulce); 5–6 jsou na nich nezávislé v kódu UI
a staví na tvaru dat z 1–4.

| # | PR | Obsah | Dotčené soubory | Testy | Riziko |
|---|---|---|---|---|---|
| 1 ✅ | `feat(architektura): cesta bez počtů lidí` — hotovo v tomto PR | Zrušit `count` a `rate` (validátor, odvození, typy, trychtýř, karta kroku, docs, skill api.md). Kontrola dat bez `count` před sloučením (§3.4). | `site_metadata.py`, `journeys.py`, `types.ts`, `journeys.ts`, `JourneyFunnel*.tsx`, `JourneyStepCard.tsx`, docs §3.2/§6, `api.md` | `test_site_metadata.py` (count odmítnut), `test_journeys.py`, `test_node_architecture.py`, `journeys.test.ts`, `derived-journeys.test.ts` | Nízké; jediné riziko = ručně uložená cesta s `count` zablokuje uložení mapy. |
| 2 ✅ | `feat(architektura): cesta nese proměnu A → B` — hotovo v tomto PR | `actor`, `pointA`, `pointB` na cestě; výřez je nese; trychtýř a editor cesty je ukazují / zadávají. | `site_metadata.py`, `journeys.py`, `node_architecture.py`, `types.ts`, `journeys.ts`, `JourneyFunnel.tsx`, `JourneyFunnelEditor.tsx`, docs §3.2/§4, `karta-pro-agenty.md`, `api.md`, `opora_read.py` | validátor (limity, prázdné vynechat), `test_node_architecture.py` (klíče, nic se nedoplňuje), `test_assignment_scope.py` (contextVersion beze změny), `journeys.test.ts` | Nízké. |
| 3 ✅ | `feat(architektura): krok nese posun a námitku` — hotovo v tomto PR | `shift` + `objection` místo `experience`; nový `_fit` (§4.3). | stejné jako 2 + `JourneyStepCard.tsx`, `page-journeys.ts`, `PageJourneys.tsx` | `test_node_architecture.py` (ořez: každý stupeň zvlášť, determinismus), validátor, `journeys.test.ts`, `page-journeys.test.ts` | Střední: ořez musí zůstat deterministický; testy na přesné pořadí. |
| 4 ✅ | `feat(architektura): krok nese ověřitelný signál via` — hotovo v tomto PR | `via {do, section?, text?}`, `journey.via-unknown`, sousedé ve výřezu nesou `via`, šipka trychtýře ukazuje signál, karta kroku „Jak sem přijde“. | `site_metadata.py`, `map_check.py`, `journeys.py` (předat `via`), `node_architecture.py`, `types.ts`, `journeys.ts`, `JourneyFunnelLink.tsx`, `JourneyStepCard.tsx`, docs §3.2/§4/§5, `api.md` | validátor (první krok jen `open`, ostatní ne), `test_map_check.py`, `test_node_architecture.py`, `journeys.test.ts` | Nízké–střední: výběr sekce předchozí stránky v kartě kroku závisí na `after`. |
| 5 | `feat(architektura): sekce říká, čím posouvá` + Detail stránky | volitelné `moves` v sekci (validátor, `page-site.ts`, `PageSectionsEditor`, výřez `page.section.moves`); záložka **Stránka** v Detailu prvku s editorem sekcí a řádkou řetězu u komponenty. | `site_metadata.py`, `node_architecture.py`, `types.ts`, `page-site.ts`, `PageSectionsEditor.tsx`, `ElementDetail.tsx`, nový dílek v `element-detail/`, `agent-context.ts`, `ArchitectureEditor.tsx` (`onSavePage`), docs §3.1/§4 | `test_site_metadata.py` (sekce bez/s `moves`, staré sekce dál platné), `test_node_architecture.py`, `test_node_brief.py`, `page-site.test.ts`, `agent-context.test.ts` | Střední: `moves` mění `contextVersion` (záměrně); dávka plánu agenta musí `moves` přijmout v návrhu sekcí – ověřit `canvas_plan*`. |
| 6 | `feat(architektura): editor stránky ukazuje úsek cesty` | Pruh navigace domény v hlavičce plátna, úsek cesty aktivní stránky s úpravou kroku, pruh sekcí s počtem komponent. | nový dílek `page-editor/journey-slice/`, `PageEditor.tsx`, `ArchitectureEditor.tsx`, `page-editor/README.md`, `architecture-editor/README.md` | `page-slice.test.ts` (sousedé, odbočky, stránka na více cestách, chybějící stránka), prohlížeč nad izolovanými daty | Střední: `ArchitectureEditor` má 190 řádků, přidání props musí zůstat skládáním; plátno nesmí ztratit `measured` (React Flow) – úsek je mimo plátno. |

Etapa 8 (harness, `lastRun`, konvence `data-opora-section`) zůstává samostatným dodatkem; tento návrh jí dává
vstup (`via`).

## 8. Otázky pro člověka

1. **A/B na cestě, nebo jednou na aplikaci?** Doporučuji **na cestě** (`actor`, `pointA`, `pointB`): různé cesty
   mají různé zákazníky a NN/g radí jeden pohled na mapu. Aplikace bez cest pak A/B nemá.
2. **Nahradit `experience` dvojicí `shift` + `objection`?** Doporučuji **ano** a bez migrace (pole je z dnešního
   #101, živý backend ho nenačetl). Alternativa: nechat `experience` jako volný text a přidat jen `shift` – méně
   práce, ale agent dostane posun a námitku slité.
3. **Rozbor sekcí jen v Detailu Editoru stránky, nebo i dál ve formuláři stránky na mapě domény?** Doporučuji
   **obojí nad stejným dílkem** `PageSectionsEditor` (mapa domény = rychlé založení stránky, Detail = rozbor
   s komponentami a `moves`); pokud chcete jedno místo, sekce z formuláře mapy domény odebrat a nechat jen Detail.

## Zdroje

[cci]: https://www.christenseninstitute.org/theory/jobs-to-be-done/
[hbr]: https://hbr.org/2016/09/know-your-customers-jobs-to-be-done
[forces]: https://jobstobedone.org/the-four-forces/
[strategyn]: https://strategyn.com/jobs-to-be-done/
[odi2]: https://www.koji.so/docs/outcome-driven-innovation-odi
[vpc]: https://www.strategyzer.com/library/the-value-proposition-canvas
[nng101]: https://www.nngroup.com/articles/journey-mapping-101/
[nngcjm]: https://www.nngroup.com/articles/customer-journey-mapping/
[sb]: https://storybrand.com/
[sbnotes]: https://grahammann.net/book-notes/building-a-storybrand-donald-miller
[bab]: https://www.campaignmonitor.com/email/bab-copywriting
[schwartz]: https://www.shortform.com/blog/customer-awareness/

- Christensen Institute, *Jobs to Be Done* (teorie, definice „progress … within particular circumstances“): <https://www.christenseninstitute.org/theory/jobs-to-be-done/>
- C. M. Christensen, T. Hall, K. Dillon, D. S. Duncan, *Know Your Customers' „Jobs to Be Done“*, HBR 2016 (ověřen jen úvod, text za paywallem): <https://hbr.org/2016/09/know-your-customers-jobs-to-be-done>
- B. Moesta, C. Spiek, *The Four Forces*: <https://jobstobedone.org/the-four-forces/>
- Strategyn (A. Ulwick), *Jobs-to-be-Done* (desired outcomes jako metriky): <https://strategyn.com/jobs-to-be-done/>; skladba výroku jen sekundárně: <https://www.koji.so/docs/outcome-driven-innovation-odi> [nejisté]
- Strategyzer (A. Osterwalder), *The Value Proposition Canvas*: <https://www.strategyzer.com/library/the-value-proposition-canvas>
- S. Gibbons, *Journey Mapping 101*, NN/g, 2018: <https://www.nngroup.com/articles/journey-mapping-101/>
- K. Kaplan, *When and How to Create Customer Journey Maps*, NN/g, 2016: <https://www.nngroup.com/articles/customer-journey-mapping/>
- D. Miller, *Building a StoryBrand* (2017); web <https://storybrand.com/>; sedm kroků ze shrnutí <https://grahammann.net/book-notes/building-a-storybrand-donald-miller> [nejisté]
- Before–After–Bridge, praktický popis bez doloženého původu: <https://www.campaignmonitor.com/email/bab-copywriting> [nejisté]
- E. Schwartz, *Breakthrough Advertising* (1966, nedostupná); pět úrovní povědomí ze shrnutí <https://www.shortform.com/blog/customer-awareness/> [nejisté]
