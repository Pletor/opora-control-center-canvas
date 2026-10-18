# Storyboard karty

Storyboard je samostatný mód plátna vedle Velína (`mode=storyboard`, bez inspektoru a bez doku). Patří kartě (`kind: "node"`):
momenty jsou zároveň režijní poznámky a klíčové stavy animace. Člověk ke každému momentu napíše, co tam chce jinak (`comment`),
případně nakreslí šipky a poznámky; agent je dostane v `node-brief`. Kontrakt: `docs/storyboard-karty.md`.

Rozvržení (mřížka `bar / layers strip / layers stage form / layers timeline form`): nahoře lišta, pod ní pás momentů, vlevo pás vrstev,
uprostřed snímek s osou, vpravo formulář momentu, v rohu snímku malý náhled celku.

- `components/StoryboardWorkspace.tsx` – rodič módu: výběr karty (`selectedNode` aplikace, změna → `onOpenNode`), značky karet se storyboardem.
- `components/StoryboardEditor.tsx` – editor jedné karty: drží koncept, čas, přehrávání (jediný `requestAnimationFrame`), výběr momentu, nástroj a viditelné vrstvy; jen on ukládá.
- `components/StoryboardBar.tsx` – lišta: výběr karty, nástroje plátna, Uložit (hned; jinak se ukládá samo), Načíst znovu / Obnovit, Otevřít v okně, Kreslit k momentu, Stáhnout, Smazat, stav.
- `components/CardPicker.tsx`, `components/StoryboardStart.tsx` – roletka karet; výběr animace a „Založit storyboard“.
- `components/MomentStrip.tsx` – pás momentů s miniaturami, časem a názvem, „+“ přidá moment v čase `t`.
- `components/LayerRail.tsx` – pás vrstev s miniaturou každé vrstvy a přepínačem; poslední vrstva „Šipky a poznámky“. Viditelnost se neukládá.
- `components/StoryboardStage.tsx` – `<canvas>`: jen viditelné vrstvy v čase `t` + overlay šipek, je-li zapnutý; klik a tažení hlásí callbacky.
- `components/MiniPreview.tsx` – malý náhled se všemi vrstvami, klik přepíná 240/420 px. `components/PaintThumb.tsx` – sdílená miniatura.
- `components/SketchOverlay.tsx` – skica momentu: překryv přes plátno s `DrawingWorkspace` ve vrstvě `sb/<karta>/<moment>`; v režimu jen ke čtení ukáže PNG. Nic neukládá.
- `components/MomentTimeline.tsx` – osa s markery, playhead, posuvník, ▶/❚❚, „+ moment zde“.
- `components/MomentForm.tsx` – přání nahoře s přepínačem „Odpovězeno“ (úprava textu přání ho vrací na `false`), anotace momentu, pak popis a pole `state` podle `fields` animace.
- `components/StoryboardSide.tsx` – pravý sloupec: u `animation: "kod"` záložky „Moment | Kód animace | Podklady“, u šablony „Moment | Podklady“ a nad nimi tlačítko „Použít jako vlastní kód“; štítek Podklady nese počet nevyřízených. `components/CodePanel.tsx` – zdroj modulu (≥ 24 řádků), název, `fields` a `layers` jako JSON, „Použít“, chyby a pomalé kreslení pod editorem.
- `logic/storyboard-model.ts` – typy, `stateAt` (interpolace + ease), úpravy momentů a anotací, `serialize`, `validate`, `annotationSentence`.
- `logic/storyboard-layout.ts` – karty do výběru, vrstvy (`layersOf`), přepínání viditelnosti, výchozí viditelnost.
- `logic/sketch-backdrop.ts` – podklad skici (snímek animace zamčený, předchozí skica 30 %, `customData.storyboardBackdrop`), `sketchLayer`, nejbližší předchozí skica.
- `logic/sketch-files.ts` – render snímku do PNG, `fileId` (SHA-1) a nahrání přes `/api/drawing-file`. `logic/use-sketch-images.ts` – PNG skic podle `fileId` (`/api/drawing-files`) jako `Image`, mezipaměť. `logic/use-sketch-session.ts` – otevření skici, export `exportToBlob` → `moment.sketch` → uložení storyboardu.
- `logic/annotation-overlay.ts` – kreslení a hit-test šipek a poznámek (bez Reactu).
- `logic/use-storyboard-store.ts` – GET/POST `/api/storyboard`, revize (ref, nikdy zastaralá), `dirty`, čas posledního uložení, stav „Změněno jinde“ při 409.
- `logic/use-storyboard-autosave.ts` + `logic/storyboard-autosave.ts` – automatické ukládání: platný koncept se uloží 700 ms po poslední změně (změna během ukládání hned po něm, při konfliktu se čeká na Obnovit) a při odchodu z karty nebo módu i při zavření stránky (`fetch` s `keepalive`); prohlížeč varuje jen, když uložení selhalo, je v konfliktu nebo je koncept chybný. „Uložit“ uloží hned.
- `logic/storyboard-status.ts` – text štítku stavu v liště („Neuloženo · ukládám za chvíli“, „Ukládám…“, „Uloženo HH:MM · 2 komentáře čekají na agenta“) a české skloňování počtu komentářů.
- `logic/animations/` – registr `ANIMATIONS` (`kulicka`, `ritual-bodu-nula`); animace dodá `fields`, `layers`, `defaults()`, `paint(…, visible)` a případně `interpolate`.
- `logic/code-module.ts` – kontrakt kódu animace: zprávy Workeru, `buildModuleSource`, `checkExports`, `describeError`, `parseCodeDraft`. `logic/code-animation.worker.ts` – Worker: Blob URL + `import()`, `OffscreenCanvas`, bez `fetch`/`XMLHttpRequest`/`importScripts`/`WebSocket`, měří `paint` (nad 50 ms zpráva `slow`). `logic/code-animation-host.ts` – hlavní vlákno: `load`, `paint`, `dispose`, sekvenční fronta, nejnovější požadavek první. `logic/use-code-animation.ts` – Worker po dobu storyboardu z kódu, chyba a obnova plátna při příchodu snímku. `logic/animations/code.ts` – `codeAnimation` (AnimationDef nad Workerem s mezipamětí snímků na jeden `board`), prázdná šablona `EMPTY_CODE`.
- `logic/animations/*.source.ts` – textová podoba šablon (`kulicka`, `ritual-bodu-nula`) jako samostatný ES modul; `source-helpers.ts` sdílí `stateAt`.
- `logic/render-package.ts` + `assets/render-package/` – „Balíček pro render“: `storyboard.json`, `animation.js`, `CLAUDE.md`, `render.py`, `index.html` stažené jako pět souborů (ZIP bez nové závislosti nejde). Statické soubory pocházejí z prototypu `storyboard-kulicka`, `index.html` a `render.py` jsou upravené na modul `animation.js`.
- `components/AssetPanel.tsx` – panel Podklady: nahrání obrázku a karta každého podkladu s náhledem, účelem, cílem, momentem, barvou, pokynem, stavem a Smazat. `logic/asset-upload.ts` – `checkAssetFile`, `newAsset`, `patchAsset`. `logic/sketch-files.ts` nahrává obrázky přes `uploadImage` (`uploadPng` je jeho PNG varianta).
- `styles/storyboard.css` – bloky `storyboard`, `code-panel`, `scene-panel`, `scene-frame` a `asset-panel`.

Skica: tlačítko „Skica“ v liště (jen u momentu s `id` od backendu) vyrenderuje snímek `t`, nahraje ho a otevře kreslení s podkladem; po „Uložit kresbu“ se scéna vyexportuje do PNG a zapíše do `moment.sketch`. Vrstva „Skica“ (`skica`) v pásu vrstev kreslí PNG přes animaci pod šipkami; `imageStale` ukáže štítek „Náhled neaktuální“. Malba (Photopea) se neimplementuje.

Nová animace = soubor v `logic/animations/` (včetně `layers` a `*.source.ts`), zápis do registru a stejné id v backendovém `ANIMATIONS`.

Workflow: moment s neprázdným `comment` a `answered: false` má v pásu štítek „nový komentář“, štítek stavu v liště za „Uloženo HH:MM“ říká, kolik komentářů čeká na agenta. Kód ze storyboardu běží jen ve Workeru; `paint` AnimationDef kreslí hotový snímek z mezipaměti a o chybějící žádá Worker, takže Stage a miniatury zůstávají beze změny.

Podklady: člověk nahraje obrázek (PNG, JPEG nebo WebP do 10 MB, nejvýše 16) a napíše k němu, jak ho agent použije – jako texturu, kterou kreslí, nebo jen jako vzor, pro celou animaci nebo jednu vrstvu a moment, případně s barvou prvku nebo přebarvením textury. Podklad čeká na agenta (`answered: false`), dokud ho agent nepoužije; každá změna pokynu ho vrací do čekání, přejmenování ne.

Webová scéna (`animation: "scena"`, kontrakt v `docs/storyboard-karty.md`, sekce „Webová scéna“): storyboard nese celý HTML dokument (`scene {title, html, fields, layers}`). `logic/scene-document.ts` – `sceneDocument` (CSP + runtime hned za `<head>`), `forbiddenScene`, `parseSceneDraft`, ukázkový `EMPTY_SCENE` a `sceneStoryboard`. `assets/render-package/scene-runtime.js` – jediný runtime pro editor i render: `window.seek(t)` (stav momentů jako CSS proměnné, `window.scene.seek(t, state)`, CSS animace pozastavené na `t − data-t0`, schované vrstvy `data-layer`) a postMessage `board`/`seek` → `ready`/`error`. `logic/use-scene-animation.ts` – AnimationDef scény (`paint` nic nekreslí, `scene` nese srcdoc, podklady jako data URL a hlášení chyb). `components/SceneFrame.tsx` – sandboxovaný iframe (`allow-scripts`) ve velikosti storyboardu zmenšený na cílovou plochu; `StoryboardStage` ho dává pod průhledné plátno (měří `logic/use-element-box.ts`), `PaintThumb` pod canvas miniatury. `components/ScenePanel.tsx` – záložka „Scéna“ (název, dokument, pole a vrstvy jako JSON, „Použít“). Balíček pro render u scény: `storyboard.json`, `scene.html`, `index.html` (= `sceneDocument`), `render.py` (fotí viewport po `seek(t)`), `CLAUDE.md` a podklady.
