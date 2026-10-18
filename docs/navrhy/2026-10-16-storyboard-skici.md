# Skici ke storyboardu: co použít a jak to zapojit

Stav 2026-10-16. Návrh, nic se neměnilo. Navazuje na `docs/storyboard-karty.md` (mód Storyboard vedle Velína:
momenty, komentáře, šipky; animace `kulicka` a `ritual-bodu-nula`). Otázka: čím kreslit **přesnější skicu
momentu** (jak má snímek vypadat) a případně **akvarel/malbu**, aby to ovládal člověk i agent a běželo to v Opoře.
Značky: **[F]** ověřeno čtením zdroje, **[?]** neověřeno, **[D]** doporučení.

## 1. GOAL

> Každý moment storyboardu může mít **skicu**: kresbu přes snímek animace (onion-skin), kterou člověk nakreslí
> rukou a agent přečte jako data (prvky, šipky, texty) **i** jako obrázek (PNG). Agent smí skicu doplnit (šipka,
> popisek, vložený obrázek) jen se schválením člověka. Nic nového se nevymýšlí: skicu kreslí Excalidraw, který už
> v Opoře je; rastrová malba (včetně „akvarelu“) je volitelný krok přes Photopea v iframe, jehož výsledek se vrátí
> jako PNG vrstva momentu.

**Hotovo, když**
1. V módu Storyboard má vybraný moment tlačítko „Skica“: otevře Excalidraw přes plátno momentu, s podkladem
   = vyrenderovaný snímek animace v čase `t` (zamčený obrázek) a předchozí skicou v 30 % (onion-skin).
2. Skica se ukládá pod kartu a moment (`drawing_revisions`, vrstva `sb/<nodeId>/<momentId>`), do momentu se
   zapíše `sketch: {layer, fileId}` (PNG export) a `node-brief.storyboard.moments[].sketch` nese `layer`,
   `fileId` a textový souhrn prvků (`"3 šipky, 2 texty: „tady zrychlit“, „kroužek až sem“"`).
3. Agent čte skicu: `opora_read.py drawing --layer sb/<nodeId>/<momentId>` (JSON prvků) a PNG přes
   `GET /api/drawing-files?ids=`. Agent píše skicu jen přes `opora_write.py /api/drawing` (nová zápisová cesta,
   schvaluje člověk, souhrn „Skica momentu <t> s · +N prvků“).
4. „Malovat v Photopea“ otevře iframe s PNG snímku + PNG skici jako vrstvami; po „Hotovo“ se PNG vrátí a uloží
   jako `paint: {fileId}` momentu; vrstva „Malba“ v pásu vrstev ji zobrazí pod šipkami. Bez internetu tlačítko
   hlásí „Photopea není dostupná“, zbytek funguje.
5. `uv run pytest backend`, `npm test`, `npm run build` projdou; kontrakt v `docs/storyboard-karty.md` §Skica.

## 2. Co jsem prozkoumal

| Kandidát | Co to je | Licence / kód | Integrace | Data pro agenta | Verdikt |
|---|---|---|---|---|---|
| **Excalidraw** (už v Opoře, `@excalidraw/excalidraw 0.18.1` [F] `package.json:14`) | vektorová skica: freedraw s tlakem, šipky, text, obrázky, rámečky | MIT, v repu | `DrawingWorkspace` (`frontend/editor/canvas/drawing`), scéna v SQLite `drawing_revisions` per `layer`, obrázky `drawing-file` [F] | JSON prvků + `exportToBlob` PNG/SVG | **[D] jádro skic** |
| **Photopea** (photopea.com) | rastrový editor ve stylu Photoshopu, vrstvy, štětce, PSD | zdarma s reklamou; API zdarma; whitelabel jen účet Distributor (cena [?]); není open-source, self-host [?] | iframe `https://www.photopea.com#<JSON>` (`files`, `script`, `environment`), `postMessage`: řetězec = skript, `ArrayBuffer` = soubor, odpověď `"done"`; `app.activeDocument.saveToOE("png")` vrátí `ArrayBuffer` [F podle api docs] | jen PNG/PSD; skript z prohlížeče, ne z backendu | **[D] volitelná malba**, závislost na cizí službě |
| **Sudo Aquarelle** (sudoaquarelle.com) | simulátor akvarelu (Curtis 1997, Kubelka-Munk) | žádný repozitář ani licence nalezeny [?]; hostovaná aplikace | žádné API, URL parametry ani postMessage [?]; iframe bez výměny dat | žádná; export PNG [?] | **nepoužít**, jen inspirace vzhledu; případně dotaz autorovi (@lionel_mora) na licenci |
| **open-note** (`…\02.Opora-control-center\open-note`) | nekonečný list pro poznámky, vanilla JS, Electron, 39,8k LOC [F] | **PolyForm Noncommercial 1.0.0** [F] `LICENSE.md` → blokuje komerční použití i odvozeniny | 90 `<script>` v jednom globálním scope, pevná DOM ID, bez API, bez buildu [F] `docs/architecture.md:42-55` | JSON v IndexedDB, bez PNG/SVG exportu listu | **nepoužít** (licence, žádné API, bez snímků/onion-skin) |

Pozn. k open-note: jediná zajímavá část je výpočet šířky tahu z rychlosti (`js/paper/ink.js:28-91`, ~60 řádků),
ale i ta spadá pod nekomerční licenci. Excalidraw má tlak pera ve freedraw přímo.

## 3. Jak to zapojit (bez nového editoru)

### 3.1 Skica momentu = Excalidraw ve vrstvě momentu
- Moment dostane stabilní `id` (dnes se identifikuje jen `t`); `storyboard.py` ho doplní při validaci.
- `canvas_service.drawing` dnes pouští jen `layer` = existující uzel (`canvas_service.py:139`, `:204`). Přidat
  prefixovanou vrstvu `sb/<nodeId>/<momentId>`: ověří, že uzel existuje a moment je ve storyboardu; jinak 409.
  Scéna i obrázky jdou stejnou cestou jako dnes (`DrawingStore`, `validate_scene`, `drawing-file`).
- Frontend: v módu Storyboard tlačítko „Skica“ u vybraného momentu otevře `DrawingWorkspace` v překryvu přes
  plátno (stejná komponenta, props `layer="sb/…"`, `readOnly`). Před otevřením rodič vyrenderuje snímek `t`
  do PNG (`canvas.toDataURL`, už se používá pro miniatury), nahraje ho `POST /api/drawing-file` a vloží jako
  zamčený `image` prvek na pozadí; předchozí moment se skicou se vloží jako druhý zamčený obrázek s `opacity: 30`
  (onion-skin). Po uložení scény rodič zavolá `exportToBlob` → `drawing-file` → `moment.sketch = {layer, fileId}`
  → `POST /api/storyboard`.
- Pás vrstev dostane vrstvu „Skica“ (kreslí PNG `sketch.fileId` přes animaci, pod šipkami).
- `node-brief`: `brief_section` doplní ke každému `sketch` souhrn prvků z `DrawingStore.read` (počty podle `type`,
  texty `text` prvků, šipky s popisky) – agent čte bez obrázku, obrázek má přes `fileId`.

### 3.2 Agent kreslí do skici
- `/api/drawing` do `WRITE_ROUTES` (`approvals.py`, `opora_write.py`) se souhrnem „Skica <karta> · vrstva sb/…
  · N prvků“; payload přesně `{project, workspace, layer, expected_revision, scene}` jako dnes [F]
  `canvas_service.py:141-147`. Agent přidává prvky Excalidraw JSON (`arrow`, `text`, `freedraw`, `image`);
  `validate_scene` už hlídá typy a velikost [F] `drawings.py:84`.
- Skill: `references/api.md` sekce „Skica momentu“, `opora_read.py drawing --layer`, příklad šipky s popiskem.
- PNG ze skici agenta vyrobí až prohlížeč při dalším otevření (nebo tlačítko „Obnovit náhledy“); backend
  Excalidraw nerenderuje. V briefu je to označené `sketch.imageStale: true`.

### 3.3 Malba (akvarel) = Photopea v iframe, volitelně
- Feature `frontend/editor/storyboard/paint/` (`PhotopeaFrame.tsx`, `logic/photopea-bridge.ts` + test): iframe
  `https://www.photopea.com#` + JSON `{files: [snímek PNG data URI, skica PNG data URI], environment: {theme, lang:
  "cs", …}}`; po načtení `postMessage` skript `app.activeDocument.saveToOE("png")` na tlačítko „Hotovo“; příchozí
  `ArrayBuffer` → `drawing-file` → `moment.paint = {fileId}`. Ověřovat `event.origin === "https://www.photopea.com"`.
- Jen člověk; agent dostane PNG. Reklamy v iframe zůstávají (whitelabel = placený účet Distributor [?]).
- Akvarelový vzhled: Photopea má štětce a režimy prolnutí; věrná simulace jako Sudo Aquarelle není. Vlastní
  WebGL akvarel nestavět (pravidlo: stavět jen na zjištěné mezery).

### 3.4 Co se nemění
Model momentů, animace `seek(t)`, `/api/storyboard`, schvalování, Kreslení jako samostatný mód.

## 4. Kroky (každý s kontrolou člověka)

| Krok | Rozsah | Ověření |
|---|---|---|
| 1 Kontrakt | `docs/storyboard-karty.md` §Skica a §Malba, `id` momentu, tvar `sketch`/`paint` v briefu | čtení |
| 2 Backend | vrstva `sb/…` v `canvas_service.drawing`, `id` momentu, `sketch`/`paint` ve validaci, souhrn v briefu, `/api/drawing` do schvalování + skill | `uv run pytest backend`, skill testy |
| 3 Frontend skica | tlačítko Skica, překryv `DrawingWorkspace`, podklad + onion-skin, export PNG, vrstva Skica | `npm test`, `npm run build`, screenshot |
| 4 Frontend malba | Photopea iframe + most, vrstva Malba, stav offline | test mostu s falešným `postMessage` |
| 5 Živě | karta Rituál bodu nula: skica k „Nález“, agent přidá šipku přes `opora_write.py`, brief ji nese | `node-brief` |

Odhad: krok 2–3 jeden den práce subagentů, krok 4 půl dne. Krok 4 lze odložit; GOAL body 1–3 a 5 stojí bez něj.

## 5. Otevřené otázky pro člověka
1. Photopea: stačí zdarma s reklamou v iframe, nebo zjistit cenu Distributor účtu?
2. Sudo Aquarelle: napsat autorovi dotaz na licenci a embed? Bez odpovědi zůstává jen inspirací.
3. ~~Má agent smět zakládat skicu sám?~~ Rozhodnuto: ano, agent skicu zakládá i mění; člověk do ní sahá a usměrňuje komentáři a šipkami.
