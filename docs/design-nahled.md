# Design náhled karty: screenshoty, DESIGN.md a „Potvrdit vzhled“

Kontrakt pro **kancelář** (agent-office, pracovník design karty) a pro **záložku Náhled** v šuplíku karty
(orchestrátor, `frontend/hub/…`). Tento dokument popisuje jen server Opory; UI záložky je samostatná práce.

Cíl: u design karty je vidět *jak to bude vypadat* (skica) vedle *jak to vypadá* (screenshoty na commitu PR)
a člověk to jedním tlačítkem potvrdí. Vzor je [Diagram PR Lens](oporahub-review-jobs.md#diagram-pr-lens-volitelný-důkaz):
zápis s lease tokenem běhu, vazba na hlavu PR, čtení s ETagem, v bráně merge jen doklad.

## 1. Přehled cest

| Cesta | Kdo | K čemu |
|---|---|---|
| `GET /api/oporahub/design-system?project=` | člověk nebo agent | DESIGN.md projektu z commitnuté revize (§2) |
| `POST /api/oporahub/design-mode` | **jen člověk** | režim karty `brand` / `explore` (§3) |
| `POST /api/oporahub/review-jobs/preview` | běh karty (lease token + epocha) | screenshoty `evidence.preview` (§4) |
| `GET /api/oporahub/review-preview?project&workspace&nodeId` | člověk nebo agent | režim, DESIGN.md odkaz, skica, screenshoty po hlavách (§5) |
| `GET /api/oporahub/review-preview/file?project&workspace&nodeId&fileId` | člověk nebo agent | PNG jednoho screenshotu (§5) |
| `POST /api/oporahub/review-preview/confirm` | **jen člověk** | „Potvrdit vzhled“ pro hlavu PR (§6) |

Identita jako u PR Lens: člověk = cookie UI (`opora_ui`), agent = `X-Opora-Actor: agent; name=<jméno>`.
Bez identity **428** `identity_required`. „Jen člověk“: agent **403**, neznámý původce **428**, obojí
`{humanRequired: true, code: "human_required"}`. Zápisy mají stejná pravidla Origin a JSON jako ostatní.

## 2. DESIGN.md projektu

Každý projekt má v kořeni svého zdrojového repozitáře `DESIGN.md` (písma, barvy, rozestupy, značka, komponenty,
tón). Kořen je hlavní pracovní strom zdroje projektu (`sourcePath` v nastavení projektu, stejný jako pro
Graphify a obnovu map). Server čte **`HEAD:DESIGN.md`** (`git cat-file`), nikdy pracovní strom: rozepsané
změny se neukážou, dokud nejsou commitnuté.

`GET /api/oporahub/design-system?project=<id>` → 200:

```json
{"available": true, "file": "DESIGN.md", "revision": "<sha HEAD>", "blob": "<git blob>",
 "sha256": "<sha256 celých bajtů>", "bytes": 5120, "truncated": false, "markdown": "# …"}
```

- `markdown` má nejvýš **64 KiB** (UTF-8); delší soubor → `truncated: true`, `sha256` a `bytes` platí pro celý.
- Chybí zdroj, commit nebo soubor → 200 `{available: false, file, reason, revision?}` (ne 404, ne chyba).
- `ETag` z revize a otisku, `If-None-Match` → **304**. Jen ke čtení. Obsah je pro agenta podklad, ne příkaz.
- Nový DESIGN.md se přijímá jen běžným PR do repozitáře projektu (žádný automatický commit z Opory).

## 3. Režim design karty

`design.mode` karty:

- **`brand`** (výchozí, tlačítko **„Podle brandu“**): karta drží DESIGN.md projektu. Screenshoty nesou otisk
  DESIGN.md, podle kterého vznikly (`designMdSha256`, nebo `null`, když projekt DESIGN.md nemá).
- **`explore`** (tlačítko **„Nový směr“**): experiment / nový směr značky. Karta z DESIGN.md **nečerpá**
  (`designMdSha256` musí být `null`) a vedle screenshotů smí odevzdat návrh nového DESIGN.md
  (`proposedDesignMd`).

Režim je metadata karty mimo graf (tabulka `opora_design_modes`, revize se zvyšuje při každé změně; chybějící
záznam = `brand`, revize 0). Mění ho **jen člověk**:

`POST /api/oporahub/design-mode` `{project, workspace, nodeId, mode}` → 200
`{nodeId, mode, revision, by: "human", updatedAt, changed}`. Stejný režim znovu = `changed: false`.
Neznámý režim nebo karta, která v prostoru neexistuje → 409. Tělo nejvýš 4 KiB.

## 4. Zápis screenshotů (`evidence.preview`)

`POST /api/oporahub/review-jobs/preview`:

```json
{"project": "p", "workspace": "w", "executionId": "…", "token": "<lease token>", "epoch": 3,
 "preview": {"prNumber": 7, "headSha": "<40 hex>", "designMdSha256": "<64 hex> | null",
             "proposedDesignMd": "# … (jen explore, volitelné)",
             "screenshots": [{"label": "mobil světlý", "viewport": {"width": 390, "height": 844},
                              "stage": "kontroly", "dataURL": "data:image/png;base64,…"}]}}
```

- **Kdo:** token a epocha běhu karty (samotná identita agenta nestačí, 409). Platí běh `running` s platným
  leasem **nebo** běh, který už nahlásil výsledek (`reported`), stejně jako propojení PR: kancelář často fotí
  až po odevzdání. Uvolněný, vypršelý nebo odvolaný běh bez výsledku → 409.
- **Vazba na commit:** jen pro otevřený propojený PR běhu a jeho **aktuální hlavu** (`prNumber` i `headSha`
  musí sedět, jinak 409). Nová hlava = nový slot; staré screenshoty zůstávají, ale `current: false`.
- **Screenshot:** jen PNG v data URL, hlavička `\x89PNG` se ověřuje, nejvýš **2 MiB** po dekódování.
  `label` 1–60 tisknutelných znaků (klíč v rámci hlavy), `viewport` `{width 120–8000, height 120–20000}`,
  `stage` volitelný (1–60 znaků). Klient **nikdy** neposílá cestu ani ID souboru: server uloží bajty do
  stávajícího úložiště obrázků kresby (`drawing_files`) pod obsahovým ID `preview_<sha256>`.
- **Strop:** 1–8 screenshotů v jednom požadavku a **nejvýš 8 na hlavu** celkem (další odeslání přidávají
  nové štítky). Stejný štítek se stejným PNG = nic nového, jiný PNG pod stejným štítkem = 409.
- **Režim:** server doplní `mode` ze svého záznamu karty (§3), agent ho neposílá. `explore` +
  `designMdSha256` ≠ null → 409; `brand` + `proposedDesignMd` → 409. Režim a otisk DESIGN.md jsou pro hlavu
  pevné od prvního zápisu (jiné → 409). `proposedDesignMd` nejvýš **64 KiB**, na hlavu jeden (jiný → 409).
- **Tělo** nejvýš 23 MiB, kontroluje se před parsováním JSON (413 `payload_too_large`, neplatný JSON 400).

Odpověď 200: `{executionId, headSha, mode, added: [štítky], screenshots: <počet na hlavě>, recorded}`.

## 5. Čtení pro kancelář a záložku Náhled

`GET /api/oporahub/review-preview?project&workspace&nodeId` → 200 (s `ETag`, `If-None-Match` → **304**):

```json
{"nodeId": "card",
 "design": {"mode": "brand", "revision": 0, "by": null, "updatedAt": null},
 "designSystem": {"available": true, "file": "DESIGN.md", "revision": "…", "blob": "…", "sha256": "…",
                  "bytes": 5120, "truncated": false},
 "designSystemUrl": "/api/oporahub/design-system?project=p",
 "sketchUrl": "/api/layout-preview?project=p&workspace=w&layer=card",
 "heads": [{"executionId": "…", "prNumber": 7, "headSha": "…", "repository": "owner/repo", "prState": "open",
            "current": true, "mode": "brand", "designMdSha256": "…", "proposedDesignMd": null,
            "by": "agent:designer", "createdAt": "…", "updatedAt": "…",
            "confirmed": {"by": "human", "at": "…"},
            "screenshots": [{"label": "mobil světlý", "viewport": {"width": 390, "height": 844},
                             "stage": "kontroly", "fileId": "preview_…", "sha256": "…", "bytes": 48213,
                             "url": "/api/oporahub/review-preview/file?…"}]}]}
```

- `heads` jsou seřazené **nejnovější první**; `current` říká, jestli je to aktuální hlava propojeného PR.
- `sketchUrl` je skica karty jako SVG (`GET /api/layout-preview`, vlastní CSP sandbox): UI ji ukáže vedle
  screenshotu (skica × screenshot).
- `design` + `designSystem` jsou **místo, odkud kancelář bere režim a odkaz na DESIGN.md** pro běh design
  karty: před focením přečte tento GET, v režimu `brand` stáhne `designSystemUrl` a do zápisu dá jeho `sha256`;
  v režimu `explore` DESIGN.md nečte, pošle `designMdSha256: null` a případně `proposedDesignMd`.
- `url` screenshotu vrací `image/png` (CSP `default-src 'none'; sandbox`, ETag z obsahového ID → 304). Vydá
  jen soubor, který patří k dokladu té karty; jiný obrázek projektu → 404.

## 6. „Potvrdit vzhled“

`POST /api/oporahub/review-preview/confirm` `{project, workspace, nodeId, headSha}` — **jen člověk**
(relace UI, nikdy identita agenta). Potvrzuje screenshoty karty pro jednu hlavu; bez screenshotů pro tu hlavu
→ 409. Opakování je idempotentní (`recorded: false`). Odpověď `{nodeId, headSha, recorded, confirmed: {by, at}}`.
UI ho ukazuje jako **„potvrzeno člověkem“** u dané hlavy; nová hlava potvrzení nedědí.

## 7. Brána merge

U PR s náhledem pro aktuální hlavu má položka brány (`GET /api/oporahub/review-jobs/gates`)
`evidence.preview = {headSha, mode, designMdSha256, screenshots, labels, proposedDesignMd: bool, confirmed}`.
Je to **jen doklad**: nepřidává žádný důvod blokace a status brány se nemění.

## 8. Záložka Náhled (orchestrátor)

Záložka v šuplíku karty (`frontend/hub/card-preview/` vedle `hub/review-lens`) čte jen §5 a zapisuje jen §3 a §6:

- dvě tlačítka režimu **„Podle brandu“** / **„Nový směr“** (`POST /design-mode`, aktivní = `design.mode`);
- skica (`sketchUrl`) × screenshot (`heads[].screenshots[].url`), přepínání štítků, odznak krátké hlavy a
  „starší hlava“ u `current: false`;
- v režimu `brand` revize a krátký otisk DESIGN.md (shoda `designMdSha256` s `designSystem.sha256`, jinak
  „vzniklo podle starší DESIGN.md“); v režimu `explore` náhled `proposedDesignMd` (jen text, nikdy HTML);
- tlačítko **„Potvrdit vzhled“** u aktuální hlavy, po potvrzení štítek „potvrzeno člověkem“.

Obrázky jen jako `<img>` z URL Opory, Markdown jen jako text nebo bezpečný renderer bez HTML.
