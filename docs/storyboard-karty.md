# Storyboard karty: kontrakt

Stav 2026-10-16, krok 1 (kontrakt před kódem). Vychází z prototypu `P:\opora-piskoviste\storyboard-kulicka`
(storyboard = momenty jako režijní poznámky **a zároveň** klíčové stavy animace; jediná funkce `seek(t)`).

## Proč

Člověk popíše animaci moment po momentu a ke každému momentu napíše, co tam chce jinak. Agent dostane
storyboard v `node-brief` a netvoří naslepo. Data storyboardu patří **ke kartě** (uzel `kind: "node"`), aby je
nesl `node-brief`; **editor je samostatný mód plátna „Storyboard“ vedle Velína** (rozhodnutí 2026-10-16, ne
záložka v detailu karty: detail je úzký a storyboard potřebuje celou plochu). Rozvržení editoru se inspiruje
Mental Canvas Draw: vlevo svislý pás vrstev s náhledy, nahoře vodorovný pás momentů jako záložek s miniaturami,
uprostřed plátno, vpravo dole malý náhled celku, vpravo komentář a šipky momentu.

## Datový model

Soubor `projects/<pid>/canvas/workspaces/<wid>/storyboards/<nodeId>.json` (cesta přes `ProjectFolder`,
nová metoda `storyboard(wid, node_id)`). Chybějící soubor = karta storyboard nemá.

```json
{
  "schema": "opora.storyboard/1",
  "animation": "kulicka",
  "title": "Kulička – odraz",
  "duration": 12, "fps": 60, "size": {"w": 1920, "h": 1080},
  "ground": 0.8, "background": "#101418",
  "moments": [
    {
      "t": 2.3, "title": "Dopad 1",
      "shows": "Kulička se na podlaze rozplácne, stín je nejostřejší.",
      "changes": "Odraz vzhůru, lehce doprava.",
      "comment": "Chci výraznější squash, aspoň o třetinu plošší než teď.",
      "id": "m-3f9a1c2e",
      "sketch": {"layer": "sb/5de58307-10f5-4783-8089-9a9fa3b609db/m-3f9a1c2e", "fileId": "a1b2…", "imageStale": false},
      "ease": "out",
      "state": {"x": 0.5, "y": 0.745, "r": 0.055, "color": "#f4b942", "opacity": 1, "contact": true},
      "annotations": [
        {"kind": "arrow", "from": {"x": 0.5, "y": 0.72}, "to": {"x": 0.56, "y": 0.42}, "text": "odraz sem, ne kolmo"},
        {"kind": "note", "at": {"x": 0.5, "y": 0.8}, "text": "stín nejostřejší tady"}
      ]
    }
  ],
  "revision": 3,
  "updatedAt": "2026-10-16T12:00:00Z"
}
```

| Pole | Význam | Mez |
|---|---|---|
| `animation` | id z registru animací; v1 jen `kulicka` | musí být v registru (backend i frontend) |
| `duration`, `fps`, `size` | délka, snímková frekvence, rozměr plátna renderu | 1–120 s; 24–60; 320–4096 px |
| `moments[]` | seřazené podle `t`, `t` v `[0, duration]` | 1–200 momentů |
| `title`, `shows`, `changes` | název, co divák vidí, co se mění do dalšího momentu | každé do 500 znaků |
| `id` | stabilní id momentu `m-<8 hex>`, doplní backend | regulární výraz |
| `sketch` | `{layer, fileId, imageStale}` skica momentu v Excalidraw, viz §Skica | nepovinné |
| `comment` | **přání člověka k momentu** (co má být jinak); jediné pole, které je pro agenta pokyn | do 2000 znaků |
| `ease` | `linear \| in \| out \| inout \| hold`, platí od tohoto momentu k dalšímu | výčet |
| `state` | klíčový stav animace; **pole určuje animace** v registru (`fields`), ne storyboard. `kulicka`: `x`, `y` (0–1), `r` (0–0.5), `color` `#rrggbb`, `opacity` 0–1, `contact` bool | do 32 klíčů; čísla konečná, řetězce do 100 znaků, bool |
| `annotations[]` | **šipky a poznámky člověka přes snímek momentu**: `arrow` (`from`, `to`, `text`), `note` (`at`, `text`); souřadnice 0–1 | do 20 na moment; `text` do 200 znaků |
| `revision` | číslo zápisu (CAS), vrací ho GET a vyžaduje POST | celé číslo ≥ 0 |

Pravidla: bez `comment` je moment jen klíčový snímek, UI to ukáže (prázdný komentář šedě „bez přání“).
Poslední moment smí být kopií prvního (smyčka), nevynucuje se. Stažený soubor je přímo čitelný pro
`render.py` z prototypu (stejné klíče; navíc `schema`, `comment`, `sketch`, `revision` renderer ignoruje).

## API (`backend/api/editor/storyboard_routes.py`, logika `backend/editor/storyboard/storyboard.py`)

| Volání | Vstup | Výstup |
|---|---|---|
| `GET /api/storyboard?project&workspace&nodeId` | | `{storyboard: {...} \| null, revision: int, readOnly: bool, animations: [{id, label}]}` |
| `POST /api/storyboard` | `{project, workspace, nodeId, expected_revision, storyboard}`; `storyboard: null` = smazat | `{revision}` |

Chyby: neznámý projekt/workspace/uzel, uzel jiný než `kind: "node"`, neplatný storyboard, stará revize
(„Storyboard se změnil v jiném okně. Obnovte ho.“) a zápis v Mainu → `ValueError` → 409 `{"error"}` (vzor
`drawing` v `canvas_service.py`). Zápis pod `graph_lock_for(pid)` + `lock_for(pid)`, atomický zápis souboru.

`node-brief` dostane sekci `storyboard` jen když soubor existuje: `{animation, duration, moments: [{t, title,
shows, changes, comment, sketch, state, annotations: [{kind, from, to | at, text}]}]}`. Šipky jdou agentovi i jako
věta v poli `annotationsText` (`„šipka z (0.50, 0.72) do (0.56, 0.42): odraz sem, ne kolmo“`), aby je přečetl bez
kreslení. `TRUST.instructions` přibude `storyboard.moments[].comment` a `storyboard.moments[].annotations`
(přání člověka), ostatní pole storyboardu jsou data. Schéma briefu zůstává
`opora.node-brief/1` (nová nepovinná sekce). Uzel bez storyboardu: brief beze změny.

Schvalování: `/api/storyboard` do `WRITE_ROUTES` v `approvals.py` i `opora_write.py` (testy synchronizaci
hlídají); souhrn `Storyboard <nodeId> · N momentů · <title>` (smazání: `Storyboard <nodeId> · smazat`).

## Frontend (`frontend/editor/storyboard/`)

Mód `storyboard` (`WorkspaceMode`, `WORKSPACE_MODES` za `map`, popisek „Storyboard“, ikona v `MODE_ICONS`).
V `App.tsx` se místo plátna vykreslí `<StoryboardWorkspace>` (jako `ControlTower` u módu `map`), bez inspektoru
a bez doku; URL nese `mode=storyboard&node=<id>`. „Otevřít v okně“ = stejná URL v novém tabu.

- `components/StoryboardWorkspace.tsx` – rodič módu: props `{project, workspace, graph, selectedNode, readOnly,
  onOpenNode, onDraw}`. Nahoře lišta: výběr karty (uzly `kind: "node"` prostoru, karty se storyboardem označené),
  výběr animace a „Založit storyboard“ pro kartu bez něj, Uložit / Načíst znovu / Otevřít v okně / Kreslit k
  momentu / Stáhnout storyboard.json / Smazat, stav (Uloženo · Neuloženo · Změněno jinde → Obnovit). Rodič drží
  koncept, revizi, `dirty`, `t`, vybraný moment, vybranou anotaci, nástroj, viditelné vrstvy; GET/POST
  přes `logic/use-storyboard-store.ts`. Přehrávání (`requestAnimationFrame`) jen tady, posouvá `t`.
  Koncept se ukládá sám (`logic/use-storyboard-autosave.ts`): platný a ne jen ke čtení 700 ms po poslední změně,
  změna během ukládání hned po něm, při 409 se čeká na Obnovit; „Uložit“ jen uloží hned a štítek stavu ukazuje
  „Neuloženo · ukládám za chvíli“ / „Ukládám…“ / „Uloženo HH:MM · N komentářů čeká na agenta“. Při odchodu z karty
  nebo módu se neuložený platný koncept uloží (`api()`), při zavření stránky přes `fetch` s `keepalive`; prohlížeč
  varuje před zavřením jen, když uložení selhalo, je v konfliktu nebo je koncept chybný.
- `components/MomentStrip.tsx` – **vodorovný pás momentů nahoře** jako záložky: každá položka je miniatura
  snímku (`paint` do malého canvasu při změně momentu), čas a název; vybraná svítí; „+“ přidá moment v čase `t`;
  tažením se moment nepřesouvá (čas se mění ve formuláři).
- `components/LayerRail.tsx` – **svislý pás vrstev vlevo** s miniaturou každé vrstvy (jen ta vrstva vykreslená
  na průhledné) a přepínačem viditelnosti; vrstvy dává animace (`layers`) plus vrstva „Šipky a poznámky“.
  Viditelnost je jen pohled editoru, neukládá se.
- `components/StoryboardStage.tsx` – plátno uprostřed, kreslí `paint` jen s viditelnými vrstvami a overlay
  anotací vybraného momentu; nástroje Vybrat / Umístit / Šipka / Poznámka jako dnes.
- `components/MiniPreview.tsx` – **malý náhled vpravo dole**: celý snímek se všemi vrstvami v aktuálním `t`
  (když člověk vrstvy schová, tady vidí celek), klik ho zvětší/zmenší.
- `components/MomentTimeline.tsx` – osa s markery a posuvníkem pod plátnem (zůstává z dnešní verze).
- `components/MomentForm.tsx` – vpravo: komentář „Co tu chci jinak“ nahoře, šipky a poznámky, pole momentu,
  pole `state` podle `fields` animace (zůstává).
- `logic/storyboard-model.ts`, `logic/annotation-overlay.ts`, `logic/animations/*` – beze změny modelu; `AnimationDef`
  přibývá `layers: [{id, label}]` a `paint(ctx, W, H, state, t, board, visible: Set<string>)`. `kulicka`: `pozadi`,
  `stin`, `kulicka`; `ritual-bodu-nula`: `pozadi`, `koule`, `jadro`, `prekryv`.
- `styles/storyboard.css` – blok `storyboard` s prvky `__strip`, `__strip-item`, `__strip-item--selected`,
  `__layers`, `__layer`, `__layer--hidden`, `__stage`, `__mini`, `__form`, `__comment`, `__status`; mřížka
  `grid-template: "bar bar bar" auto "layers strip strip" auto "layers stage form" 1fr "layers timeline form" auto`.
- Záložka v detailu karty a obrazovka `screen=storyboard` se **ruší** (mazat i testy a styly, žádné sirotky).
- Kreslit k momentu: `onDraw(nodeId)` → `enter(nodeId)` + `setMode("drawing")` (vrstva kresby = karta).
- Stažení: Blob `storyboard.json` čitelný pro `render.py` prototypu.

## Praktický příklad: Rituál bodu nula (Tajemství Opory)

Druhá animace v registru je `ritual-bodu-nula`: čekací animace věštby z TO (`frontend/app/src/pages/oracle/components/zero-point/ZeroPoint.tsx`
+ `meta-ball/MetaBall.tsx`, časování v `hooks/useDivination.ts:102-157`, vše CSS keyframes a `setTimeout`, čas
zvenčí řídit nejde). V Opoře ji nese karta `[task] Rituál bodu nula — plynulá animace čekání`
(`5de58307-10f5-4783-8089-9a9fa3b609db`, workspace `36fd9bc1d1b4455087b315271f2fb42d`, projekt
`41a6776519694319a3aaf7ff453c3dfc`). Adaptér kreslí na `<canvas>` totéž, ale ze `seek(t)`: osm zlatých rozmazaných
koulí (volné vznášení → sjetí do kruhu), zlaté jádro se třemi kroužky (pulz), blik a rozšíření kroužků při nálezu,
překryv s textem. Pole `state`: `gather` 0–1 (vznášení → kruh), `pulse` 0–1 (rychlost pulzu), `found` 0–1
(blik a rozšíření kroužků), `overlay` 0–1 (průhlednost překryvu), `label` text překryvu, `core` 0–1 (záře jádra).
Výchozí storyboard = dnešní časová osa (0 s sjetí, 2 s text mizí, 3 s nález, 4 s výsledek, 6 s klid), aby člověk
rovnou psal komentáře a šipky k tomu, co má být jinak. Originální kód TO se nekopíruje ani nemění.

## Skica momentu (Excalidraw) a malba (Photopea)

Rozhodnuto 2026-10-16 (`docs/navrhy/2026-10-16-storyboard-skici.md`): skicu kreslí Excalidraw, který v Opoře je;
nový editor se nestaví. Malba přes Photopea je volitelný krok 4 a čeká na rozhodnutí člověka.

- Každý moment má stabilní `id` (`m-<8 hex>`), backend ho doplní při validaci, frontend ho nevymýšlí.
- Skica = kresba ve vrstvě `sb/<nodeId>/<momentId>` v `drawing_revisions` (`GET/POST /api/drawing?layer=`).
  `canvas_service.drawing` tuto vrstvu pustí, když uzel existuje a moment je ve storyboardu uzlu; jinak 409.
  Scéna i obrázky jdou stejně jako dnes (`validate_scene`, `drawing-file`).
- Moment nese `sketch: {layer, fileId, imageStale}`: `fileId` je PNG export skici (`drawing-file`), `imageStale`
  = `true`, když scénu změnil někdo bez exportu (agent); při `imageStale: true` smí být `fileId` prázdný.
- **Agent skicu zakládá i mění sám** (rozhodnutí člověka 2026-10-16): POST `/api/drawing` na vrstvu `sb/…`
  momentu bez `sketch` ho založí jako `{layer, fileId: "", imageStale: true}`; člověk pak do téže skici kreslí,
  přepisuje a doplňuje komentáře a šipky momentu. Každý zápis agenta schvaluje člověk. Pole `sketch` jako text se ruší; co bylo v `sketch`
  textu, zůstává jen v `shows`.
- V módu Storyboard: tlačítko „Skica“ u vybraného momentu otevře `DrawingWorkspace` v překryvu přes plátno
  (`layer="sb/…"`). Před otevřením rodič vyrenderuje snímek `t` do PNG, nahraje ho a vloží jako zamčený `image`
  prvek na pozadí (`locked: true`, `opacity: 100`); skica předchozího momentu (pokud má `fileId`) jde jako druhý
  zamčený obrázek s `opacity: 30` (onion-skin). Podkladové prvky mají `customData: {storyboardBackdrop: true}`
  a při dalším otevření se vymění za čerstvé. Po uložení scény rodič udělá `exportToBlob` → `drawing-file` →
  `moment.sketch` → `POST /api/storyboard`.
- Pás vrstev má vrstvu „Skica“ (PNG `sketch.fileId` přes animaci, pod šipkami); miniatura momentu v pásu ji
  obsahuje.
- `node-brief.storyboard.moments[].sketch` = `{layer, fileId, imageStale, summary}`, kde `summary` je souhrn
  prvků ze scény: počty podle typu a texty (`"3 šipky, 2 texty: „tady zrychlit“, „kroužek až sem“"`).
- Agent skicu čte `opora_read.py drawing --layer sb/…` a PNG přes `drawing-files?ids=`; píše jen přes
  `opora_write.py /api/drawing` (nová zápisová cesta, souhrn „Skica <nodeId> · sb/… · N prvků“), vždy se
  schválením člověka. Zápis agenta nastaví `sketch.imageStale = true` (backend při POST `/api/drawing` na vrstvu
  `sb/…`).
- Malba (Photopea, krok 4): `moment.paint: {fileId}` a vrstva „Malba“; zatím se neimplementuje.

## Vlastní animace z kódu (agent i člověk nejsou omezeni registrem)

Rozhodnutí člověka 2026-10-16: agenti mají tvořit **libovolné** animace a upravovat je; Opus je má umět ztvárnit
jako v původním postupu „video z kódu“ (`seek(t)`, Playwright, ffmpeg). Registr `kulicka` / `ritual-bodu-nula`
jsou jen šablony.

- Třetí druh animace `animation: "kod"` nese modul přímo ve storyboardu:
  `code: { "source": "<JS>", "fields": [...], "layers": [...], "title": "..." }` (`source` do 64 kB, ES modul bez
  importů). Modul exportuje `fields`, `layers`, `defaults()` (nepovinné) a `paint(ctx, W, H, state, t, board,
  visible)`; stejný kontrakt jako `AnimationDef` v registru, aby šel kód mezi registrem a storyboardem přenášet.
- Frontend kód spouští v **Web Workeru s `OffscreenCanvas`** (`logic/code-animation-host.ts`): modul se načte přes
  `Blob` URL + `import()`, worker nemá DOM ani `fetch` (přepsané na `undefined`), každé `paint` má limit 50 ms,
  chyba modulu se ukáže v pásu vrstev („Kód animace selhal: <zpráva>“) a plátno zůstane prázdné. Hlavní vlákno
  posílá `{state, t, visible, size}` a dostává `ImageBitmap`. Miniatury používají tutéž cestu.
- Backend validuje jen tvar (`source` řetězec, limity, `fields`/`layers` jako v registru); kód nespouští.
  `node-brief.storyboard` nese `code.source` celý (agent ho čte a přepisuje) a `code.fields`.
- Agent kód píše přes `POST /api/storyboard` (schvaluje člověk; souhrn uvede „kód animace: N řádků“).
- Člověk kód může upravit v textovém poli „Kód animace“ v módu Storyboard (záložka u formuláře), uložení =
  `POST /api/storyboard`; chyby se ukáží ihned (worker modul znovu načte).
- „Použít jako šablonu“: z registru do `code` (zdroj registru se zkopíruje do storyboardu, od té chvíle je vlastní).
- Export „Balíček pro render“ (`storyboard-<nodeId>.zip` nebo složka stažená jako více souborů): `storyboard.json`,
  `animation.js` (z `code.source` nebo z registru), `CLAUDE.md` s postupem (seek(t), Playwright 60 fps, ffmpeg,
  stilly, tři nejhorší problémy), `render.py` a `index.html` z prototypu. Opus v prázdné složce vyrenderuje video.
  Prototyp `P:\opora-piskoviste\storyboard-kulicka` je zdroj těch souborů (kopie v `frontend/editor/storyboard/assets/`).

## Podklady: nahrané obrázky, textury a barvy (2026-10-16)

Člověk v módu Storyboard (záložka „Podklady“ vpravo) nahraje obrázek (PNG/JPEG/WebP do 10 MB, uložený jako
`drawing-file` projektu, `fileId` = SHA-1 data URL) a ke každému napíše, co s ním má agent udělat. Žádný nový správce
souborů: obrázky leží v `drawing_files` jako obrázky kreseb a skic.

```json
"assets": [{"id": "a-1a2b3c4d", "name": "šachovnice", "fileId": "<sha1>", "mimeType": "image/png",
            "purpose": "texture", "target": "objekt", "momentId": "", "color": "#ff0000", "colorUse": "tint",
            "note": "Koule má tuto texturu, lehce do červena.", "answered": false}]
```

| Pole | Význam | Mez / chyba |
|---|---|---|
| `id` | stabilní `a-<8 hex>`, doplní backend | regulární výraz |
| `fileId`, `mimeType` | nahraný obrázek; backend při uložení ověří, že v projektu je a že typ sedí s uloženým | neexistující nebo jiný typ = 409 „Obrázek podkladu … není nahraný“ / „udává …, nahraný obrázek je …“ |
| `purpose` | `texture` = agent obrázek kreslí (`drawImage`/`createPattern`), `reference` = jen se jím řídí | výčet |
| `target` | id vrstvy animace (`code.layers` u `kod`, u šablon `pozadi/stin/kulicka`, `pozadi/koule/jadro/prekryv`); prázdné = celá animace | neznámá vrstva = 409 s výčtem vrstev |
| `momentId` | moment, kterého se týká; prázdné = všechny | neznámý moment = 409 |
| `color`, `colorUse` | barva `#rrggbb` a její význam: `object` = **barva prvku/objektu**, `tint` = **přebarvení textury** (multiply přes obrázek). Barva bez `colorUse` je chyba; bez barvy je `colorUse` prázdné | žádné hádání barev z obrázku |
| `note` | pokyn člověka k podkladu (do 500 znaků), pro agenta pokyn | |
| `answered` | agent podklad použil. Backend při uložení vrátí `false`, kdykoli se proti uloženému stavu změní `fileId`, `purpose`, `target`, `momentId`, `color`, `colorUse` nebo `note` (zaškrtnuté „odpovězeno“ nelze podstrčit s novým pokynem) | nejvýše 16 podkladů |

Totéž znovuotevření platí pro momenty: `answered: true` drží jen při nezměněném `comment`, `annotations` a
`sketch` (PNG i `imageStale`); zápis skici agentem i člověkem (`mark_sketch_stale`) nastaví `answered: false`.
Sekce nese `revision` a `updatedAt` posledního uložení a bez otevřených komentářů `workflow.next` dodá „naposledy uložen …“, aby agent uměl říct, že novější neuložený komentář nevidí. Otevřený moment pro `workflow` je každý s komentářem, šipkou **nebo** skicou bez odpovědi; `workflow.openAssets`
a věta `next` jmenují podklady bez odpovědi. Smazaný storyboard nechá v souboru náhrobek `{deleted, revision}`,
takže revize neklesá na 0 (CAS nejde obejít).

- **Brief**: `node-brief.storyboard` nese `layers` (id vrstev), `assets[]` s `available` (obrázek v projektu je),
  `read` (`/api/drawing-files?…ids=<fileId>`) a `cli` (`opora_read.py drawing-file --id <fileId> --out <soubor>`),
  momenty mají `id`. Agent obrázek stáhne příkazem CLI a prohlédne; jen `fileId` bez cesty nestačí.
- **Kód animace** dostává obrázky jako 8. parametr `paint(ctx, W, H, state, t, board, visible, images)`,
  `images[asset.id]` je `ImageBitmap` (editor) nebo `HTMLImageElement` (render balíček). Host je vyrábí z načtených
  obrázků a předává Workeru (`{type: "assets"}`); kód animace sám nic nenačítá. Worker běží pod CSP
  `default-src 'none'; script-src blob:; worker-src blob:; connect-src 'none'` (hlavička na
  `/assets/code-animation.worker-*.js`): statický i dynamický import z http(s) včetně vlastního původu, vnořený
  Worker i `fetch` prohlížeč zablokuje; textová kontrola `forbiddenImport` dá jen českou větu dřív.
  Vypnuté globály (`fetch`, `XMLHttpRequest`, …) zůstávají druhou pojistkou.
- **Jeden obrázek všude**: plátno, miniatury i náhled kreslí tentýž snímek z Workeru; balíček pro render přidá
  `asset-<id>.<png|jpg|webp>` a `storyboard.json` u podkladu `file`; `index.html` obrázky načte před `seek(t)` a bez nich
  není nikdy `STORYBOARD_READY` (render.py skončí kódem 2 „Chybí soubory podkladů“). Žádný tichý fallback na barvu
  ani šablonu; `seek(t)` je deterministické (obrázky načtené jednou).
- `drawing-file`: obsah souboru musí odpovídat `mimeType` (hlavička PNG/JPEG/WebP/GIF); stejné `id` s jiným obsahem
  je 409 (dřív tichý `INSERT OR IGNORE`).
- Po uložení si editor stáhne kanonický storyboard (doplněná `id`, případné `answered: false`) a převezme ho jen
  tehdy, když člověk mezitím koncept nezměnil.

## Webová scéna: hotová stránka jako animace (`animation: "scena"`, 2026-10-16)

Šablony a kód (`kod`) kreslí **náčrt** v Canvas 2D: hodí se, když se ladí artefakt, symbol nebo pohyb jednoho prvku.
Pro web ale vzniká stránka (HTML + CSS + JS) a schválit se má **to, co se nasadí**. Proto existuje druhý druh animace,
**webová scéna**: storyboard nese celý HTML dokument scény, editor ho přehrává v sandboxovaném iframe, miniatury, náhled
i render balíčku ukazují tentýž dokument. Člověk pracuje s dílky scény (vrstvy = prvky DOM), říká, jak se mají hýbat
(komentáře, šipky, skici, pole stavu), a snímek je přesně snímek webu. Oba druhy žijí vedle sebe; karta má vždy jen jeden.

### Datový model

```jsonc
{ "schema": "opora.storyboard/1", "animation": "scena", "duration": 6.6, "fps": 60, "size": { "w": 1400, "h": 480 },
  "scene": {
    "title": "Rituál bodu nula – web",
    "html": "<!doctype html><html lang=\"cs\">…celý dokument…</html>",   // 1–262144 znaků, bez řídicích znaků kromě \t \n \r
    "fields": [ { "key": "glow", "label": "Záře jádra", "kind": "number", "min": 0, "max": 1, "step": 0.01 } ],  // ≤ 32, jako u kódu
    "layers": [ { "id": "pozadi", "label": "Pozadí" }, { "id": "koule", "label": "Koule" } ]                         // 1–16, id [a-z][a-z0-9-]{0,31}
  },
  "moments": [ … stejné jako u ostatních animací … ], "assets": [ … ] }
```

Backend (`validate_storyboard`): `scena` vyžaduje objekt `scene` (tvar jako `code`, místo `source` je `html`), `animation_layers`
bere `scene.layers`, podklady míří na tyto vrstvy. `brief_section` nese `scene` {title, html, fields, layers} celé, aby agent
mohl dokument upravit a zapsat zpět přes `/api/storyboard` (CAS revizí, schválení člověka jako u všeho ostatního).

### Kontrakt dokumentu scény (co musí autor, člověk nebo agent, dodržet)

1. **Samostatný dokument**: všechno inline (CSS, JS, fonty jen `data:`). Žádný `<script src>`, `<link>`, `@import`,
   `url(http…)`, `fetch`, `XMLHttpRequest`, `WebSocket`, `import()`. Editor i render stránku zavřou CSP
   (`default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; connect-src 'none'`);
   `forbiddenScene(html)` dá českou větu dřív, než CSP mlčky zablokuje.
2. **Dílky = vrstvy**: prvek, který patří vrstvě, nese `data-layer="<id>"` ze `scene.layers`. Schovaná vrstva dostane
   `visibility: hidden` (runtime vloží styl), rozvržení se nemění. Prvek bez `data-layer` je vidět vždy.
3. **Čas řídí host**: scéna definuje `window.scene = { seek(t, state) }` a z `t` (sekundy) odvodí fázi, třídy a hodnoty.
   Žádný `setTimeout`, `setInterval` ani `requestAnimationFrame` pro děj. CSS animace a přechody se smějí používat: prvek, od
   kterého se počítá jejich start, nese `data-t0="<s>"` (nejbližší předek; bez něj 0). Runtime po `seek` každé CSS animaci
   i přechodu nastaví `currentTime = (t − t0)·1000 ms` a pozastaví ji, takže stejný `t` dá vždy stejný snímek (i při skoku zpět).
4. **Stav momentů**: runtime před `seek` zapíše každý klíč stavu jako CSS proměnnou na `<html>` (`--glow: 0.7`; řetězec beze změny,
   ano/ne jako 1/0) a tentýž stav předá do `seek(t, state)`. Pole `scene.fields` jsou tedy ovládací prvky scény: člověk je
   v momentech posouvá, scéna je čte z CSS nebo z `state`.
5. **Podklady**: `window.STORYBOARD_ASSETS = { "<assets[].id>": "data:image/…" }` je nastavené před prvním `seek`
   (editor z načtených obrázků, render ze souborů balíčku); scéna ho použije jako `src` nebo `background-image`.
6. **Rozměr**: dokument se vykresluje ve viewportu `size.w × size.h` px a má ho vyplnit (`html, body { margin: 0; width: 100%; height: 100% }`).
   Náhledy jsou jen zmenšený týž dokument (`transform: scale`), nic se nekreslí znovu.

### Runtime (`frontend/editor/storyboard/assets/render-package/scene-runtime.js`, jeden zdroj pro editor i render)

`sceneDocument(html)` (`logic/scene-document.ts`) vloží na začátek `<head>` meta CSP a runtime jako první `<script>`; výsledek je
`srcdoc` iframe v editoru i `index.html` v balíčku. Runtime:

- `window.seek(t)`: stav z `window.STORYBOARD_DATA` (stejná interpolace jako `stateAt`), CSS proměnné, `scene.seek(t, state)`,
  synchronizace CSS animací podle `data-t0`, styl schovaných vrstev. `window.STORYBOARD_READY = true`, jakmile existuje
  `window.scene.seek`; jinak chyba „Scéna nedefinuje window.scene.seek(t, state).“
- Zprávy z hosta (`postMessage`): `{ type: "board", board, hidden: [id…], assets: { id: dataURL } }`, `{ type: "seek", t }`;
  odpovědi `{ type: "ready" }`, `{ type: "error", message }` (výjimka v `seek` nebo chyba stránky). V balíčku zprávy nejsou
  potřeba: `render.py` vloží `STORYBOARD_DATA` a volá `window.seek(t)`.

### Editor

- `SceneFrame` (`components/SceneFrame.tsx`): `<iframe sandbox="allow-scripts" srcdoc=…>` ve velikosti `size` zmenšený na
  cílové rozměry; dostává `t`, skryté vrstvy, podklady a hlásí chybu nahoru. Plátno (`StoryboardStage`) leží přes něj
  průhledné: šipky, poznámky a skica se kreslí dál na canvas, kliky bere canvas. `PaintThumb` u scény vrátí iframe + canvas
  (pás momentů, pás vrstev s jednou vrstvou, náhled celku).
- `useSceneAnimation(board, images)` skládá `AnimationDef` (`paint` nic nekreslí; `scene` = dokument) a chybu scény.
- Záložka **Scéna** v pravém panelu (`ScenePanel`): název, HTML dokument, pole a vrstvy jako JSON, „Použít“ (`parseSceneDraft`).
  Založení: volba „Webová scéna“ s ukázkovým dokumentem (`EMPTY_SCENE`), který kontrakt předvádí (dvě vrstvy, `data-t0`, `seek`).
- „Použít jako vlastní kód“ u scény není (dokument není Canvas modul).

### Balíček pro render

`storyboard.json`, `scene.html` (čistý dokument), `index.html` (= `sceneDocument(html)`), `render.py`, `CLAUDE.md`, obrázky
podkladů. `render.py` u `animation: "scena"` po `window.seek(t)` bere `page.screenshot()` celého viewportu (`size`, případně
`--size`) místo `toDataURL` plátna; síťová brána a CSP platí stejně (kód 3 při sahání mimo balíček).

### Hranice

- Scéna běží jen v sandboxu bez původu (`allow-scripts`, žádné `allow-same-origin`): nevidí Oporu, cookies ani síť.
- Jeden storyboard = jeden dokument; víc scén = víc karet. Šablony se na scénu nepřevádějí automaticky; agent dokument píše.
- Determinismus je na autorovi: `seek` nesmí záviset na reálném čase ani na pořadí volání (runtime to ověřuje jen tím, že
  animace zarovná podle `t`).

## Postupný workflow (člověk ↔ agent)

| Krok | Kdo | Co | Kde |
|---|---|---|---|
| 1 Záměr | člověk | karta s cílem animace; v módu Storyboard „Založit storyboard“ (šablona nebo prázdný kód) a první momenty s komentáři „co tu chci“ | mód Storyboard |
| 2 Návrh | agent | čte `node-brief.storyboard` (momenty, komentáře, šipky, skici, kód), navrhne momenty, skici a kód animace, zapíše přes `opora_write.py /api/storyboard` a `/api/drawing` | schválení člověkem |
| 3 Usměrnění | člověk | prohlédne výsledek (plátno, vrstvy, miniatury), dopíše komentáře, šipky, přepíše skicu nebo kód | mód Storyboard |
| 4 Iterace | agent | reaguje jen na momenty s novým komentářem; po každém kole `annotationsText` a `comment` dostávají v briefu `answered: false` (nové) / `true` (agent odpověděl v `changes`) | brief |
| 5 Hotovo | člověk | brána karty (`done.proposed` → potvrzení) | karta |
| 6 Render | Opus 5.5 / agent ve VS Code | „Balíček pro render“ → `python render.py --stills` → video a stilly; kontrola tří nejhorších problémů → zpět do kroku 3 | prototyp / složka |

## Hranice

- Vzhled a ovládání jsou jednou pro aplikaci; chování se neliší podle druhu projektu (žádná nová capability).
- Main je jen ke čtení: panel v `readOnly` zobrazí storyboard, ukládání a úpravy jsou zamčené.
- `seek(t)` je jediný zdroj snímku; render do videa zůstává v prototypu (`render.py`), aplikace video nevyrábí.
- Režim Kreslení se nemění; přibývá jen cesta, jak se do něj dostat z karty s vrstvou karty.
- Storyboard nezasahuje do Desktop v3 stavu uzlu, pipeline ani uzavření karty.

## Hotovo, když

- `uv run pytest backend`, `npm test`, `npm run build` projdou.
- Mód Storyboard vedle Velína: výběr karty, pás momentů s miniaturami, vrstvy s náhledy, plátno, malý náhled,
  formulář s komentářem a šipkami, uložení s revizí (409 → obnovit), otevření v okně, kreslení k momentu, stažení JSON.
- `node-brief` uzlu se storyboardem nese momenty s komentáři a `trust.instructions` obsahuje
  `storyboard.moments[].comment`; uzel bez storyboardu má brief beze změny.
- Zápis `/api/storyboard` přes `opora_write.py` jde do schvalování se souhrnem.
