# Karta DNA – čistá karta na plátně a popup se vším o kartě

Zadání uživatele 2026-10-08: „Karty potřebuji čisté. Když se karta rozklikne, vyskočí popup, kde budou
všechny podrobnosti a to, co po mně chceš, abych se rychle orientoval a měl vše na jednom místě.
Proklikat hlavní záložky a nemít takto velké karty. Padá mi z toho prohlížeč kvůli paměti.“
Popup je „DNA karty“: proces chronologicky i sémanticky, workflow a pipeline, propojení s GitHubem
a OporaHubem (aktuální kód a verze zadání, kdy to sedí a výstup funguje v prohlížeči). Když LLM dostane
stejnou kartu znovu, postaví ji podle všech zaznamenaných dat a cesty.

Vzor problému: karta 2.10 projektu ample (screenshot `image12.png` v kořeni hlavního repa) – na kartě
je editor důkazů s každým `checksRun` jako 5 inputů; při výběru více karet se editory mountují všem.

## 1. Karta na plátně (kompaktní, bez editorů)

Zobrazuje jen to, co je vidět na první pohled (infografika před prózou):

- hlava: typ (`[task]`…), název, stav (`ready`/`claimed`/`done`), vrstva; odznak „čeká na tebe“;
- proužek kontrolního pásu (`CardChecklist`, 10 buněk) – beze změny;
- jedna řádka indikátorů (ikona + číslo, `title` s popisem): pipeline `finished/total` (+ selhání),
  lease (agent + zbývající čas, **jeden sdílený ticker** pro celé plátno, ne `setInterval` na kartu),
  „zadání se změnilo“, commit (zkrácené SHA z `realization`), spotřeba;
- bloky jen jako řádek: číslo, titulek, tečka stavu (`met`/`unmet`/`blocked`) a **React Flow handle portů**
  (vazby musí dál fungovat, `data-block-id` zůstává kvůli kliknutí na blok);
- porty karty (`CardPorts`) beze změny.

Na kartě NESMÍ být: `EvidenceEditor`, `CardEvidence` se seznamem běhů, `SourceRealization`, `CardRules`,
`InheritedRules`, `CardFacts`, `CardChecks` editor, textarea bloků, `PortDecisionEditor`, `PortSpawnEditor`,
`SpecificationDiff`, `WorkDetails` se seznamem souborů. Vše se přesune do popupu. Kompaktní karta
je stejná pro vybranou i nevybranou kartu i pro hromadný výběr (`Board.tsx` `isSelected`).

## 2. Popup „DNA karty“

Otevření: klik na kartu (mimo `[data-block-id]` a handle). Dvojklik dál vstupuje dovnitř.
Esc / křížek zavře a **odmountuje** obsah. Nativní `<dialog>` + `showModal()` podle
`frontend/ui-kit/removal-dialog/components/RemovalDialog.tsx`; záložky ARIA tablist podle
`editor/node-detail/components/NodeTabs.tsx`. Data záložky se načtou až při jejím otevření (lazy),
velké seznamy stránkovaně (`/agent-results?before=`).

Záložky (pořadí = pořadí orientace člověka):

1. **Přehled** – cíl, stav, kdo na kartě pracuje, a hlavně **„Co po tobě chci“**: položky kontrolního pásu
   ve stavu `no`/`run` s `hint` a tlačítkem, které otevře správnou záložku (např. „kontroly → Důkazy
   a kontroly“), `loop.waitingOnHuman`, návrh uzavření (`ConfirmProposal`), další krok pipeline.
2. **Zadání** – spec (goal / non_goals / acceptance) s revizí a historií (`/api/node-spec/history`),
   text karty, bloky s podmínkami a porty, pravidla (vlastní + zděděná s původem), rozhodnutí.
3. **Proces** – časová osa (chronologicky) z: snímků zadání (assignment), převzetí (lease), etap pipeline
   s poznámkami, výstupů agentů (`resultHistory` / `agent-results`), zpráv na vazbách, rozhodnutí,
   běhů kontrol (`checksRun.at`), realizace (commit). Filtr podle sémantické skupiny:
   Zadání · Práce · Ověření · Předávky · Kód.
4. **Pipeline a workflow** – etapy (`PipelineStageRow`) s `note`, opakování (`retryOf`) a smyčky oprav,
   bloky s porty a `onMet`, vazby na předchůdce a následníky.
5. **Důkazy a kontroly** – `checks` karty (editor `ChecksEditor` – tady člověk nastavuje kontroly),
   `evidence` tests / review / merge s odkazy, tabulka `checksRun` (jen čtení; `EvidenceEditor` až
   po tlačítku „Upravit důkazy“).
6. **Kód a verze** – `sourceRef` + `source-status`, realizace (commit → odkaz na GitHub, `prUrl`,
   `verifiedAt`), formulář realizace, OporaHub (`/api/sync-report`: synced / app-ahead / repo-ahead…),
   „zadání vs. výstup“ (`assignment-status`, porovnání `SpecificationDiff`), návrh (`design`),
   scénář E2E a poslední běh („výstup funguje v prohlížeči“).
7. **DNA** – tlačítko „Kopírovat DNA karty“: Markdown balík pro LLM, ze kterého jde kartu postavit
   znovu: `node-brief` (zadání, pravidla, bloky, upstream), pipeline s poznámkami, historie výstupů,
   důkazy, rozhodnutí, realizace (commit + cesta). Logika skládání v `logic/` s testem.

## 3. Výkon (prohlížeč nesmí padat)

- `Board.tsx`: data karty stabilní mezi polly (memo podle obsahu, ne nový objekt při každém pollu);
  `memo(NodeCard)` musí reálně držet – test na `card-model` / porovnání.
- `<ReactFlow onlyRenderVisibleElements>`.
- Jeden ticker pro lease všech karet.
- Žádný `JSON.stringify` velkých struktur při renderu karty.
- Popup jen jeden (pro otevřenou kartu), obsah se při zavření odmountuje.

## 4. Pravidla

`CLAUDE.md` a `docs/pravidla-struktury.md`: feature složka (`components/`, `logic/`, `styles/`, `README.md`),
BEM CSS s příběhovým komentářem, soubor ≤ ~200 řádků, rodič ukládá (dílek hlásí callbackem), testy
`.test.ts` vedle (`renderToStaticMarkup`), logika bez Reactu v `logic/` s testem. Nové dílky:
`frontend/editor/card-dna/` (popup, záložky, časová osa, DNA export). Kontrakt karty pro agenty
(`docs/karta-pro-agenty.md`) se nemění.

## 5. Hotovo, když (GOAL)

- `npm test` zelené, včetně nových testů:
  - kompaktní karta s 200 `checksRun`, 8 bloky po 8 portech a vybraným stavem nemá v markupu
    žádný `<input>`, `<textarea>` ani `<select>`;
  - popup má 7 záložek a obsah jen aktivní záložky;
  - časová osa řadí položky chronologicky a filtruje podle skupiny;
  - DNA export obsahuje zadání, pipeline s poznámkami, důkazy, commit a cestu.
- `npm run build` zelené.
- `uv run pytest backend` – žádný nový pád (výchozí stav: 2 padající testy graphify závislé na prostředí).
- Vše, co karta dřív ukazovala, je v popupu dosažitelné (žádná funkce se neztratí).

## 6. Dokončení implementace (2026-10-08)

- Esc, křížek, změna záložky včetně klávesnice a skrytí důkazů používají jeden
  `draft-guard`: načte dirty/pending participanty stejného project/workspace,
  vyčká `flushSaveScope` a znovu ověří čistotu. Existující flush participantů dál
  používá `confirmSavedChange`. Editor označený jako blocked se neodmountuje;
  dialog ukáže důvod a člověk zvolí Uložit/Zrušit v původním formuláři. Chyba
  ukládání ponechá koncept i aktuální panel. Souběžné přechody se neskládají.
- Rozlišení klik/dvojklik nemá pevný časovač. První click ukáže nativní
  neinteraktivní `show()` náhled (`inert`, pointer-events:none), aby původní
  karta zůstala cílem dalšího clicku. `detail === 2` náhled odmountuje a vstoupí
  dovnitř; `dblclick` už akci neopakuje. Po přesunu ukazatele mimo původní kartu
  nebo interakci klávesnicí se tentýž dialog převede na `showModal()`. Esc funguje
  i v náhledu. To řeší konflikt okamžitého showModal s doručením druhého clicku,
  aniž by aplikace hádala OS interval. Bloky, porty, handles a ovládací prvky
  tuto cestu neotevírají; modifikátory zůstávají pro výběr.
- Přehled zachovává release lease, Zadání/Pipeline decision a spawn, Zadání rename.
  Shared ticker ovládá jen odpočet, nikoli claim/heartbeat/release či jejich polling.
- Kód dostává známý source-status i všechny stavy assignment z Boardu. Externí
  odkazy jsou jen HTTPS. Historie stránkuje výsledky i zprávy; export zachová
  zprávy a celý node-brief. Chybějící hodnoty se nevydávají za ověření ani undefined.
- Feature má jediný styles/card-dna.css s BEM třídami a tokeny. Kompaktní porty
  neřežou svůj handle; oříznutý je pouze dlouhý popisek.
- npm test/build používají configLoader runner (test navíc no-cache): worktree
  sdílí node_modules přes junction a ověřování nemá zapisovat cache/config do něj.

### Dosud neověřeno v prohlížeči

Skutečný pomalý dvojklik a náhled→modalita, Esc/křížek/změna tabu/skrytí se všemi
rozepsanými editory, návrat focusu, release lease proti živému serveru,
rozhodnutí/spawn/rename, port drag-to-connect a výkon při hromadném výběru.
Jednotkové a SSR testy nejsou náhradou těchto browser kontrol.
