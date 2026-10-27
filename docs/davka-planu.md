# Dávka plánu: celé zadání na plátno jedním schválením

Stav: **kontrakt** (2026-10-02). Vznikl ze skutečného běhu na Ample (session `707d5523…`, `/wayfinder` nad zadáním Jihlavy, ~35 000 znaků). Asistent běžel přes hodinu, zapsal 12 karet a výsledek agentovi nic neřekne. Důvody jsou v Opoře, ne v modelu:

| Zjištěno v běhu | Příčina | Řeší |
|---|---|---|
| „Hook zablokoval znak `>`“, „nepustí `\|`“, „příliš dlouhý příkaz“, popisy karet zkrácené, tabulky přepsané na odrážky | zápis jde jen jako `--json '<json>'` v jednom řádku příkazu; `approvals.COMMAND` zakazuje `;&\|<>$` a nový řádek | §2 koncept zápisu v souboru |
| „Musel jsem poslat znovu celý graf“ | `/api/graph` nahrazuje celý graf, karty šly po dávkách A–F, G–L | §3 `/api/canvas-plan` přidává, nenahrazuje |
| Karty mají jen název a spec; žádné bloky, porty, text, `sourceRef`, pravidla; vazby jen 7× `next` | zápis bloků, pravidel a textu jsou tři další cesty a desítky schválení; recept nic víc nežádá | §3 jedna dávka nese všechno, §4 recept s laťkou |
| Sektory Vln prázdné „až z rozhodnutí“ | recept zakládá `[task]` až po uzavření mapy | §4 kostra `[task]` karet hned ze zadání |
| Zadání Jihlavy se neuložilo („zápis souborů je vypnutý“) | asistent nesmí psát soubory, podklad nemá kam dát | §4 podklad jako text karty |

## 1. Cíl

Asistent převede dlouhé zadání a rozhovor na strom karet, ze kterého agent pochopí, **co** má postavit, **podle čeho** se to pozná a **s čím** to souvisí, a to v jedné dávce, kterou člověk schválí jedním kliknutím. Žádný text se kvůli zápisu nezkracuje.

Mimo rozsah: nové UI (ApprovalCard ukazuje souhrn, který dodá backend), automatické spuštění agenta, změna existujících karet (dávka jen přidává; úpravy dál přes stávající cesty).

## 2. Koncept zápisu v souboru

- Backend při spuštění session založí adresář konceptů `<data>/assistant-drafts/<sessionId>/` mimo repo projektu i Opory a předá ho procesu v proměnné `OPORA_DRAFTS_DIR` (vedle `OPORA_BASE_URL`, `command.py`) a jako `draftsDir` v `<opora_context>` každé zprávy. Cesty pro `Write` i `--json-file` jsou absolutní; jméno bez `:`; při povolení se ověří, že se koncept od žádosti nezměnil (sha256).
- Nástroj `Write` backend pustí **sám, bez dotazu**, jen když `file_path` po rozlišení (`resolve`, žádné `..`, žádný symlink ven) leží v adresáři konceptů té session a končí `.json`, velikost do 2 MiB. Jinak `auto_deny` jako dnes. Koncept nic nemění; mění až zápis na plátno.
- `opora_write.py … --json-file <cesta>` je pro schvalování platný, jen když cesta leží v adresáři konceptů session. Karta schválení pak ukazuje souhrn **skutečného obsahu souboru** (`payload_summary` nad načteným JSON), ne „payload ze souboru“. Soubor, který nejde přečíst nebo není JSON objekt, je `auto_deny`.
- `--json` v příkazu zůstává pro krátké zápisy beze změny.
- Adresář konceptů se smaže se zavřením session; nic z něj necommituje.

## 3. `POST /api/canvas-plan`

Jedna dávka, která na vrstvu přidá uzly, vazby, spec, text, bloky s porty a podmínkami, pravidla a rozhodnutí. Atomicky: buď projde celá, nebo nic (při chybě se nic nezapíše a odpověď řekne, která položka a proč).

```jsonc
{
  "project": "…", "workspace": "draft",
  "digest": "<digest grafu z posledního view>",   // 409 při neshodě
  "dryRun": false,                                // true = jen ověření a souhrn, nic se nezapíše
  "plan": {
    "nodes": [{
      "ref": "ingest",                    // lokální jméno v dávce, [a-z0-9-], unikátní
      "kind": "node",                     // node | sector | comment | area
      "parent": "@pilot-mapa",            // "@<existující id>" | "<ref z dávky>" | null (kořen)
      "name": "[task] Pipeline zpracování dokumentů",
      "purpose": "…",                     // podstata na kartě
      "card": { "layer": "backend", "status": "draft" }, // volitelné, jen node; stejná validace jako graf (i tech, states, section — sekce musí existovat na nejbližší stránce)
      "position": { "x": 120, "y": 240 }, // volitelné místo vložení; bez něj automatické rozložení
      "sourceRef": { "origin": "existing", "path": "api/src/…", "kind": "directory" },  // volitelné; kind directory | file
      "size": { "w": 1200, "h": 800 },    // jen area
      "spec": { "goal": "…", "non_goals": "…", "acceptance": "…" },                // limity node_specs
      "text": "…",                        // text karty (podklad: výňatek zadání), limit node-text
      "agentRole": "backend",             // volitelné
      "blocks": [{
        "ref": "formaty",
        "title": "Formáty vstupu",
        "text": "PDF (i sken s OCR), DOCX, XLSX/CSV, PPTX, MD, TXT, HTML, URL …",
        "condition": "Každý povinný formát projde a je zobrazitelný v meziformátu.",
        "ports": [{ "ref": "ok", "label": "Splněno → chunking" }, { "ref": "ocr", "label": "Sken nečitelný → OCR" }]
      }],
      "rules": [{ "kind": "must", "text": "Každý záznam nese organizaci a projekt." }]   // scope node
    }],
    "edges": [
      { "from": "vzorek", "to": "ingest", "port": "next" },
      { "from": "ingest", "to": "chunking", "port": "block", "block": "formaty", "blockPort": "ok" },
      { "from": "@433bed1b-…", "to": "pilot", "port": "flow" }
    ],
    "decisions": [{ "node": "ingest", "text": "Extrakce: docling-serve (MIT) + Tesseract cs.", "pinned": false }]
  }
}
```

Pravidla:

- **Jen přidává.** Existující uzly se odkazují `@id` (rodič, konec vazby), ale dávka je nemění. Nová ID přidělí backend (UUID), odpověď vrátí `refs: {ref → id}` a `blocks: {ref/blockRef → blockId}`.
- **Poloha:** bez `position` backend položí nové uzly do mřížky (odhad karty 360 × 240, mezera 96, 6 na řádek) pod existující uzly téže vrstvy. Volitelné `position: {x,y}` přijímá konečná čísla do absolutní hodnoty 1 000 000: volný bod se zachová, při kolizi se hledá blízké místo a poté běžná mřížka. Výsledný graf znovu projde validací. Rozměry skutečně rozbalené karty může zvětšit její obsah; rozložení nenahrazuje vizuální ověření.
- **Oblast jako `parent`:** oblast nesmí být rodičem, proto `parent` ukazující na oblast znamená „polož dovnitř“: karta leží na vrstvě oblasti a celá v jejím obdélníku (okraj 48). Oblast je pružná: plný rámeček backend zvětší (nejdřív do šířky na 3 sloupce karet, pak po řádcích dolů) a nový `size` oblasti uloží v téže dávce. Růst zastaví jen cizí těleso vrstvy těsně u rámečku nebo strop 20 000; pak dávka skončí chybou „zvětšete její size“. Oblast v oblasti se odmítá.
- **Druhy:** bloky, pravidla, `agentRole` a volitelné `criteria: string[]` smí jen `node` a `sector`; spec a text kterýkoli druh (i text oblasti). Kritériím backend přidělí ID a výchozí `checked: false`. Katalog ukládá své podmínky do `spec.acceptance` a stejné podmínky do `criteria` neduplikuje.
- **Uzavření:** dávka nesmí přidávat potomka do uzavřené karty ani pod jejího uzavřeného předka. Starší uložené uzly i obsah zůstávají nedotčené.
- **Aplikace a stránky:** nepovinné `site` označuje existující druhy uzlů: sektor může nést `{ "kind": "application", "environments": [{ "name": "Produkce", "host": "example.test" }] }`, uzel stránky `{ "kind": "page", "path": "/kontakt" }`. Stránka musí mít předka aplikace; běžné mezilehlé uzly a vnořené stránky jsou povolené. Host je doména nebo `localhost:port` bez protokolu a URL cesty, unikátní napříč aplikacemi projektu; jména prostředí jsou unikátní v aplikaci. Cesta stránky je absolutní, bez dotazu, fragmentu a `.` / `..` segmentů, unikátní v nejbližší aplikaci. Dvě různé aplikace mohou obě mít `/`. Metadata projdou stejnou validací při běžném uložení grafu. Prostředí sdílejí jeden strom stránek; tento zápis neprovádí DNS ani nasazení. Účel zůstává pouze v `purpose`, bez automatické kopie do pracovního `spec.goal`.
- **Validace** je stávající validace grafu, specu, textu a stavu Desktop v3 (limity, porty ≤ 8 na blok, komentář bez vazeb, `flow` jen mezi oblastmi, `block` vazba s existujícím blokem a portem zdroje). Dávka nesmí obejít žádné pravidlo, které platí pro jednotlivé cesty.
- **Limity dávky:** nejvýš 200 uzlů, 600 vazeb, 2 MiB (strop těla v `factory.py` je pro tuto cestu 2 MiB).
- **Revize:** graf podle `digest`, stav Desktop v3 podle jeho revize načtené uvnitř téže operace; spec a text nových uzlů jsou nové (revize 1; autora tabulky revizí neukládají). Id portu je jeho `ref`.
- **Hranice zápisu:** lokální projekt ukládá graf i obsah ve stejné SQLite transakci. Git workspace zapisuje graf atomickou výměnou souboru a následně potvrdí SQLite; existuje úzké okno pádu mezi výměnou souboru a potvrzením databáze. Obyčejná validační chyba nebo selhání zápisu grafu vrací databázovou transakci zpět.
- **`dryRun`** vrátí totéž co ostré volání (`refs` jako náhled, souhrn), jen nic nezapíše. Asistent ho volá před žádostí o schválení.
- **Ověření bez přepisu konceptu:** `opora_write.py /api/canvas-plan … --json-file F --dry-run` pošle obsah konceptu s `dryRun: true` bez ohledu na to, co v něm stojí; koncept se proto píše **jednou** a bez `dryRun` a ostré volání je tentýž příkaz bez `--dry-run`. `--dry-run` u jiné cesty je chyba skriptu a schvalování ho zamítne. Příkaz s `--dry-run` nic nezapíše, proto ho backend pustí bez dotazu na člověka (`approvals.classify` → `auto_allow`, jen platný koncept session). Důvod: běh `707d5523…` psal 44 kB koncept dvakrát (~20 000 výstupních tokenů navíc), jen aby přepnul `dryRun`, a na schválení pouhého ověření čekal 5–6 min.
- **Velikost konceptu:** jedna dávka = jedna oblast nebo sektor, nejvýš ~25 kB. Koncept se generuje celý jako vstup jednoho nástroje a během toho panel nevidí text; opravu chyby z ověření udělá asistent novým menším konceptem jen s opravenou částí, ne přepisem celé dávky.
- **Souhrn** (pro kartu schválení i odpověď): `„Přidá 1 oblast, 5 sektorů, 23 karet, 61 bloků, 74 portů, 38 vazeb (next 21, block 15, flow 2), 19 pravidel, 6 rozhodnutí, text u 23 karet.“`
- Cesta je v `WRITE_ROUTES` v `opora_write.py` i `approvals.py`; schvaluje ji člověk jako každý zápis.
- Router `backend/api/editor/`, logika `backend/canvas/canvas_plan.py`, test `test_canvas_plan.py` vedle.

## 4. Recept: dlouhé zadání → strom karet

Patří do skillu `opora-control-center/references/workflow.md` (nahrazuje „Recept: plán aplikace → karty“) a odkazuje se z wayfinderu i grillingu, když běží nad OPORA.

**Laťka karty.** Karta, kterou dávka založí, musí agentovi stačit bez otevírání chatu:

Tento recept platí pro rozpracování konkrétního dlouhého zadání. Ruční vložení obecné předlohy z Knihovny zakládá teprve upravitelný základ: souvislosti, kroky a šablonu ukládá jako text, bez rozbalených pracovních bloků. Úplnost konkrétního zadání se doplní v detailu karty.

1. **Text karty = podklad.** Doslovný výňatek ze zadání, který se karty týká, s názvem kapitoly („Zadání Jihlava, kap. Zpracování dat, Kroky pipeline 1–9“). Nikdy parafráze. Celé zadání leží jako text karty oblasti (nebo sektoru mapy), když ho nejde uložit do repa.
2. **Spec:** `goal` = co má po dokončení platit a čemu v cíli slouží; `non_goals` = sousední karty, které to řeší (jménem); `acceptance` = ověřitelné body převzaté z akceptačních kritérií zadání + příkazy testů projektu.
3. **Bloky = rozpad práce.** Jeden blok na jedno funkční kritérium nebo krok (u pipeline jeden blok na krok, u widgetu vzhled / chování / přístupnost / bezpečnost vložení…). `text` říká co a jak, `condition` podle čeho je blok splněný. Karta bez bloků je chyba, ne zkratka.
4. **Porty = výsledky bloku.** Každý blok, jehož výsledek ovlivní jinou kartu, má port s popiskem výsledku („Splněno → chunking“, „Sken nečitelný → OCR“) a z portu vede vazba `block` na tu kartu. Rozhodovací karta má blok na každou otázku a port na každou variantu odpovědi.
5. **Vazby = jak to bude fungovat.** `next` = pořadí hlavní linky a blokace; `block` = datový/rozhodovací tok mezi konkrétními bloky; `flow` = tok mezi oblastmi. Kdo čte jen vazby, musí poznat cestu dokumentu od nahrání po citaci ve widgetu.
6. **`sourceRef`** na existující kód, který orientace našla (`existing` s cestou), nebo `planned` pro nový modul. Bez něj karta „nezapadá“.
7. **Pravidla** `must` / `must_not` převzatá ze zadání („Každý dotaz do indexu nese organizaci a projekt“, „nesmí odpovídat z obecných znalostí modelu“).
8. **Typ v názvu** `[task] / [research] / [grilling] / [prototype]` zůstává.

**Postup asistenta:**

1. Orientace (plátno → kód → graphify → Archify → paměť), jako dnes.
2. Kostra **hned ze zadání**: oblast, sektor mapy s kartami-rozhodnutí **a** sektory vln s kartami `[task]`, které zadání popisuje (co a podle čeho poznat je známé; otevřené je jen jak). Karta `[task]`, kterou rozhodnutí ovlivní, dostane vazbu `block` z portu varianty rozhodovací karty, ne prázdný sektor.
3. Návrh jako tabulka pro člověka (karta, bloky, porty, vazby, sourceRef) a po souhlasu **jedna dávka**: koncept nástrojem `Write` do `<draftsDir>/plan.json` (absolutní cesta z `<opora_context>`; `$` v příkazu schvalování nepustí), `opora_write.py /api/canvas-plan --json-file "<draftsDir>/plan.json" --dry-run` (bez dotazu), oprava chyb, pak tentýž příkaz bez `--dry-run` → člověk schválí jednou.
4. Kontrola: `node-brief` každé nové karty; karta bez textu, bloků, vazby nebo `sourceRef` se do výsledku hlásí jako nedodělaná, ne jako hotová.

## 5. Ověření

- `test_canvas_plan.py`: dávka s oblastí, sektory, kartami, bloky s porty, vazbami všech druhů, pravidly a rozhodnutím projde a `node-brief` karty je obsahuje; chybná položka (port navíc, vazba z komentáře, neznámý `ref`, špatný digest) nezapíše nic; `dryRun` nic nezapíše; existující uzly zůstanou beze změny; poloha nových uzlů se nepřekrývá.
- `test_approvals.py`: `Write` do adresáře konceptů projde sám, mimo něj (i přes `..` a jinou session) ne; `--json-file` mimo adresář je `auto_deny`; souhrn ukazuje obsah souboru.
- `uv run pytest backend`, `npm test`, `npm run build`.
- Živě: dávka z kostry Ample (sektor Vlna 2 s ≥ 3 kartami, bloky s porty, vazby `block`) projde jedním schválením.
