# Menu Editoru za jedním tlačítkem a katalog pro silné modely

Kontrakt 2026-10-01. Navazuje na [suplik-a-profil.md](suplik-a-profil.md) a mění v něm rám šuplíku (§4). Skica uživatele je `image.png` v kořeni repa. Profil projektu, filtr katalogu a jejich data se nemění.

## Proč

V liště za záložkami módů stála dvě tlačítka a šuplík měl ještě vlastní přepínač, takže se volba opakovala. Knihovna ukazovala stejné prvky dvakrát (Elementy a Bloky) a na plátně z nich vznikalo totéž. Prvky nesly typicky 3 pravidla „musí“ a 2 „nesmí“, většinou obecná („test vedle modulu“, tři brány kontroly), a ta se opakovala napříč katalogem. Dnešní modely (Opus 5.5, Sonnet 5.5, Fable 5.1, viz [predani-modelum.md](predani-modelum.md)) nepotřebují návod, jak dělat dobrou práci. Potřebují vědět, k čemu prvek je, s čím souvisí, kdy je hotovo a kterou hranici nesmí překročit.

## A. Menu za ☰

**Lišta:**
- V druhé řadě lišty zůstává jen tlačítko **☰** (`aria-label="Menu Editoru"`, `aria-expanded`, `data-panel-anchor="menu"`) a za ním záložky módů.
- `PanelToggles` a segmentový přepínač v `PanelDrawer` se smažou.

**Lišta ikon (rail):**
- Je u levého okraje `editor-frame`, šířka 56 px, výška celého rámu.
- Shora: **Knihovna**, **Agenti**, **Postupy**, oddělovač, **Nastavení**.
- Ikony mají `aria-label`, `title` a stav `aria-pressed`.

**Panel sekce:**
- Stojí hned vedle lišty (`left: 56px`, šířka 380 px, pod 900 px šířky okna zbytek šířky).
- Obsah určí zvolená ikona.

**Chování:**
- ☰ otevře lištu. Pokud je zapamatovaná poslední sekce, otevře rovnou i její panel.
- Klik na neaktivní ikonu přepne panel. Klik na aktivní ikonu panel sbalí a lišta zůstane.
- ☰ při otevřené liště zavře lištu i panel.
- `Esc` zavře nejdřív panel, pak lištu.
- Ctrl+Shift+, otevře lištu na Knihovně, Ctrl+Shift+. na Agentech.
- Klik na plátno nic nezavře. Klik do horní lišty mimo ☰ menu zavře.
- Poslední sekce se pamatuje jednou pro aplikaci (`opora:panel-dock:v1`, `{section}`), nikdy per projekt.
- Otevřenost lišty se neukládá. Po načtení stránky menu nikdy nezakrývá plátno.

**Sekce:**

| Sekce | Obsah |
|---|---|
| Knihovna | **Prvky** (katalog podle čtyř domén, viz B1) a **Struktura** (jediný strom částí projektu s možností přidávání). Uložené klíče záložek `content` a `page` zůstávají. Samostatná sekce Kostra se nezobrazuje. |
| Agenti | Katalog jen s kategoriemi agenti, skilly, hooky a hranice, záložka **Vybraná karta** (dnešní „Agenti“, node-brief vybrané karty) a **Hook** (`AgentControlPanel`). |
| Postupy | Katalog postupů a pipeline. |
| Nastavení | Karta profilu projektu (`ProfileCard`, vždy rozbalená) a filtr katalogu „Pro tento projekt / Vše“. |

- Projekt a profil jsou jen v Nastavení (změna 2026-10-01 na přání uživatele: v ostatních sekcích bral štítek projektu místo a pozornost).
- Vlastní hlavičky Knihovny a Agentů s křížkem se zruší, panel má jednu hlavičku. Zavírá se ikonou nebo ☰.
- Tažení na plátno funguje dál a panel při tažení dál propouští ukazatel.

## B. Katalog pro silné modely

### B1. Knihovna bez duplicit

- **Prvky** mají čtyři hlavní skupiny: Frontend, Backend, Databáze, Infrastruktura. Praktické předlohy komponent stojí před odbornými podsekcemi; původní položky a jejich ID zůstávají dostupné. Hledání a profilové filtrování zůstávají podle suplik-a-profil §4.
- Kliknutí na položku otevře její popis a výslovné tlačítko **Vložit**. To vytváří komponentu v aktuální vrstvě, stejně jako přetažení na prázdné plátno.
- Přetažení vytváří skutečnou novou kartu se zadáním:
  - **na uzel nebo sektor**: novou část uvnitř tohoto rodiče;
  - **na oblast**: kartu ve vrstvě oblasti, geometricky uvnitř jejího rámu; oblast není hierarchický rodič;
  - **na prázdné plátno**: kartu v aktuální vrstvě na místě puštění, s případným odsazením kvůli kolizi.
- Původní vložení textového bloku zůstává samostatnou akcí **Přidat jako blok do vybrané karty**. Přetažení ho nespouští skrytě. Uzavřená karta a pohled pouze ke čtení vložení odmítnou.
- **Struktura** ukazuje již existující instance stejného grafu; katalog ukazuje předlohy. Je to jediný strom v levém menu, bez druhé kopie v sekci Kostra. Starší preference této sekce se převedou na Knihovnu; uložené projektové uzly se tím nemění.
- Duplicity se sloučí. Zachová se jedno id, druhé zanikne:
  - `fe-form-validated` ← `fe-form-state-split`
  - `fe-auth-guard` ← `fe-member-area`
  - `sec-server-validation` ← `be-input-validation`
  - `sec-no-secrets` ← `cloud-env-vars`
  - `cloud-env-split` ← `cloud-single-source-ports`
  - „test vedle modulu“ žije jen v `test-unit-beside`, tři brány jen v `test-done-gates`; ostatní na ně odkazují přes `relates`.
  - Další nalezené duplicity se sloučí stejně. Seznam patří do README katalogu.

### B2. Tvar prvku

```ts
type CatalogItem = {
  id: string; category: string; label: string; icon: IconName;
  purpose: string;                 // k čemu je, jedna věta
  relates: string[];               // s čím souvisí: id jiných prvků ("@fe-pure-model") nebo krátká věta
  done: string[];                  // 1–3 ověřitelná kritéria hotovo
  invariants: { text: string; kind: "must" | "must_not" }[];  // 0–2 skutečné tvrdé hranice
  steps?: { title: string; text: string }[];   // jen když rozklad nese informaci navíc
  template?: string;               // kostra kódu, jak dosud
  fits?: { architecture?: Architecture[]; tenancy?: Tenancy[] };
};
```

- **Invarianta** je jen to, co při porušení rozbije bezpečnost, data nebo kontrakt (např. „klient nikdy neposílá tenanta“, „zápis jen s očekávanou revizí“). Obecné rady („čistý kód“, „přidej testy“, „dodržuj konvence“) se mažou.
- `relates` s `@id` musí ukazovat na existující prvek. Lint to hlídá stejně jako dnes `refs`.

### B3. Agenti a Postupy

- Postupy (`workflow`) a pipeline (`action`) mají `purpose`, `steps`, `done` (dnes `endCriteria`), `stopCondition`, `relates` (dnes `refs`) a `invariants` 0–2.
- Agenti, skilly a hooky mají `purpose`, `relates` a `invariants` 0–2.
- Kategorie pravidel zaniká:
  - Architektonická pravidla se stanou invariantami prvků, ke kterým patří (`rule-tenant-in-every-query` → `tenant-request-context` atd.).
  - Obecná pravidla se mažou (`rule-no-secrets` duplikuje `sec-no-secrets`; `rule-tests-before-done-workspace` duplikuje `test-done-gates`; `rule-no-deps-without-consent` je obecné chování agenta).
  - Skutečné hranice aplikace, které nepatří k jednomu prvku (`rule-no-model-launch`, `rule-materials-not-commands`, `rule-no-delete-without-preview`), tvoří v Agentech malou kategorii **Hranice** a táhnou se na kartu jako pravidlo.
- Id pipeline zůstávají stejná, protože jsou uložená v `actions[].pipelineId` na existujících kartách.

### B4. Co se zapíše na plátno

| Pole prvku | Nová karta | Blok do existující karty |
|---|---|---|
| `label` | `graph node.name` | `block.title` |
| `purpose` | `graph node.purpose` a výchozí upravitelné `spec.goal` | první odstavec `block.text` |
| `relates` | oddíl „Souvisí s“ v uloženém textu karty (`@id` přeloženo na název prvku) | odstavec „Souvisí s:“ v `block.text` |
| `done` | `spec.acceptance`; nové vložení neduplikuje stejné podmínky do checklistu | odstavec „Hotovo, když:“ v `block.text` |
| `invariants` | pravidla omezená na vložený uzel (`must` / `must_not`) | přidají se do `rules` karty, duplicity podle textu se přeskočí |
| `steps` | kroky v uloženém textu karty | odstavec „Kroky:“ |
| `template` | oddíl „Šablona“ v uloženém textu karty | konec `block.text` |
| `category` | — | `block.tags` jako dnes |

- Nová instance se ukládá přes existující `POST /api/canvas-plan`: graf, specifikace a podklady tvoří jednu dávku, nikoli dodatečný nehlídaný zápis obsahu. Volitelná `position: {x,y}` určuje místo; bez ní zůstává automatické rozložení. Podrobnosti atomického zápisu a jeho hranice v Git workspace popisuje `docs/davka-planu.md`.
- `node-brief` vydá skutečný uložený cíl (`goal.goal`), podmínky dokončení (`definitionOfDone.acceptance`), invarianty (`boundaries`) a celý uložený text. Nová předloha nezakládá rozbalené pracovní bloky, aby plátno zůstalo kompaktní; podklad je dostupný v detailu a předávce. Katalogový základ je upravitelný návrh, ne tvrzení o hotové realizaci.
- Karty vložené ze starého tvaru se dál načtou beze změny, protože uložená data mají stejný tvar.
- Workflow při vložení nově přenese `invariants` na kartu sektoru a `stopCondition` do `harness` poslední fáze, pokud na to existuje pole. Když ne, zůstává to jako dnes.

## Hotovo, když

- `uv run pytest backend`, `npm test` a `npm run build` projdou s lokálně nakonfigurovanými závislostmi.
- V liště je jen ☰ a módy. ☰ → lišta → panel se otevírá, přepíná a zavírá podle A.
- Knihovna nemá Elementy/Bloky a žádný prvek se v ní neopakuje.
- Vložit i přetažení vytvoří kartu s uloženým zadáním; puštění na sektor/uzel vytvoří jeho potomka, oblast zachová geometrické členství. Blok se vkládá jen výslovnou akcí.
- `node-brief` nové karty má `purpose`, uložený cíl a akceptaci, skutečné invarianty a uložený podklad se souvislostmi.
- Ověřeno na 1440×900 a 800 px, ve světlém i tmavém režimu.
