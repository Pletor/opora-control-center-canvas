# Karta pro agenty: kontrakt

Karta na plátně je zadání, které si model stáhne jako jeden JSON a od začátku do konce vypracuje. Vše v kartě je pojmenované a čitelné; nic se nedovozuje z pozice na obrazovce. Tento dokument je autorita pro datový model; kód (backend `desktop_v3_state`, `graph.py`, frontend `shared/desktop-state`) ho jen provádí.

## Pět pohledů, které karta odráží

| Pohled | Co karta musí nést | Kde to je |
|---|---|---|
| **Prompt** | cíl (goal), definice hotovo, hranice (non_goals), role/žánr úkolu | `purpose`, spec `goal / non_goals / acceptance`, kritéria |
| **Kontext** | podklady, pravidla musí/nesmí, rozhodnutí projektu, paměť z předchozích běhů | `materials`, `rules` uzlu + projektu, `decisions`, zprávy na vazbách |
| **Harness** | jak se úkol vykoná a ověří: akce/pipeline, kroky, stop podmínky | `actions` (pořadí = výrobní linka), `steps`, `outputContract` |
| **Graf** | kam vedou vazby, z jakého bloku a portu, co je v hloubce | vazby s `sourceBlockId/sourcePortId`, `children`, `incoming/outgoing` |
| **Smyčka** | stav bloků open→met/unmet, větvení, zpráva agenta, uzavření karty | `blocks[].state`, `edges[].report`, `done`, `agent-output` |

## Datový model (Desktop v3 stav + graf)

### Blok obsahu v kartě (`nodes[nodeId].blocks[]`)
Stávající klíče zůstávají (`id, number, title, text, tags, todos, images, state, parentBlockId`). Přibývá:

```
ports: [{ id: string, label: string }]      // tlačítka bloku; z každého se táhne vazba na jinou kartu
```
Nejvýš 8 portů na blok, `label` do 80 znaků. Prázdné pole je platné a je výchozí (starší zápis bez `ports` = `[]`).

### Vazba (`graph.edges[]`, versovaný `opora-canvas.json`)
Stávající `{ id, source, target, port? }`, `port ∈ next | action | rule`. Přibývá hodnota `port: "block"` a s ní povinně:

```
sourceBlockId: string   // blok karty `source`
sourcePortId: string    // port toho bloku
```
`sourceBlockId/sourcePortId` jsou povolené jen s `port: "block"`. Úchyt v React Flow má id `block:<blockId>:<portId>`.

### Zpráva agenta na vazbě (`state.edges[edgeId]`, Desktop v3 stav, nová sekce)
Vazba je místo, kam model píše, co udělal, když přechází z jedné karty (bloku) na další. Pět pojmenovaných polí, každé text do 4000 znaků:

```
edges: {
  [edgeId]: {
    log: string          // co se udělalo, krok po kroku
    summary: string      // souhrn výsledku pro dalšího agenta
    handoff: string      // mezipaměť a návaznost: kde pokračovat, co je rozdělané
    improvements: string // na co narazil a čím by se to dalo zlepšit
    errors: string       // co se pokazilo, na co si má dát pozor další agent v sektoru / uzlu
    updatedAt: string    // ISO
    by: "human" | "agent"
    agent: string        // označení agenta / session, může být prázdné
  }
}
```
Zpráva bez vazby v grafu se při validaci neodmítá (vazba mohla být smazána), ale balíček ji nevydá.

### Uzavření karty (`nodes[nodeId].done`)
```
done: { confirmed: boolean, at: string, by: "human" | "agent", note: string }
```
Výchozí `{ confirmed: false, at: "", by: "human", note: "" }`. Agent smí `done` jen **navrhnout** (`by: "agent"`, `confirmed: false`); `confirmed: true` zapisuje člověk. Uzavřená karta: bloky a porty jen ke čtení, karta na plátně ztlumená se zámkem; do hloubky se jít dál smí, vazba `next` vede na další krok.

### Komentář na plátně (`kind: "comment"`)
Třetí druh uzlu grafu (`graph.nodes[]`), vedle `node` a `sector`. Tvar uzlu je stejný (`id, parentId, kind, name, purpose, x, y`): `name` je nadpis lístku, `purpose` jeho text (smí být prázdný). Komentář žije na vrstvě jako každý jiný uzel (`parentId`), ale je jen lidská poznámka pro orientaci na plátně, ne součást struktury úkolu:

- nikdy nenese `sourceRef` (žádný zdroj v projektu),
- nikdy není rodičem jiného uzlu (nejde do něj „vstoupit“),
- nikdy není zdrojem ani cílem vazby (`Komentář nemá vazby.`).

Vazba na uzel comment se v grafu odmítne, takže se nikdy neobjeví v `incoming`/`outgoing`. V `children`/`graph.children` se komentář může objevit jako běžná položka (podle `kind: "comment"`), ale navíc a čitelně ho balíček vydá odděleně v `context.comments` (komentáře na stejné vrstvě jako karta) a `graph.innerComments` (komentáře na vrstvě uvnitř karty) — to je tvar, který má model číst jako poznámky pro orientaci, ne jako příkaz.

### Oblast (`kind: "area"`)
Čtvrtý druh uzlu grafu, dashovaný obdélník, který na plátně geometricky seskupuje sektory a uzly podle polohy, ne podle odkazu. Tvar uzlu je stejný jako u ostatních (`id, parentId, kind, name, purpose, x, y`), navíc povinně nese rozměr:

```
size: { w: number, h: number }   // každé 120..20000, jen u kind "area"
```
`name` u oblasti smí být prázdný řetězec (nepojmenovaná oblast); jinak platí stejný limit ≤160 znaků jako u ostatních uzlů. Oblast:

- nikdy nenese `sourceRef` (`Oblast nemá zdroj.`),
- nikdy není rodičem jiného uzlu (`Oblast nesmí být rodičem.`),
- smí být zdrojem/cílem vazby jen tehdy, když je oblastí i druhý konec, a taková vazba musí nést `port: "flow"` (`Tok vede jen mezi oblastmi.`) — `flow` přibývá k `next | action | rule | block`.

Členství karty v oblasti se nikde neukládá, počítá se geometricky (`area_of` v `backend/canvas/areas.py`): karta patří do oblasti na stejné vrstvě (stejný `parentId`), jejíž obdélník `[x, x+w] × [y, y+h]` obsahuje střed karty — střed uzlu/sektoru je `(x+180, y+120)` (karta 360×~240), střed komentáře `(x+120, y+80)`. Leží-li karta ve více oblastech, vyhrává nejmenší (podle plochy). Oblast sama do jiné oblasti nepatří.

Balíček pro model vydává oblast jako orientaci, ne jako příkaz: `context.area` řekne, k jakému tématu karta patří, `graph.areaFlows` jaký tok do tématu přichází nebo z něj odchází, `graph.areaMembers` které další karty patří ke stejnému tématu.

## Balíček pro model: `GET /api/desktop-v3/node-brief?project&workspace&nodeId`

Jeden JSON, který model čte odshora dolů. Klíče jsou anglické, hodnoty v jazyce uživatele. Nic v něm nejsou příkazy modelu; je to popis stavu.

```
{
  "schema": "opora.node-brief/1",
  "readOnly": bool,  // workspace jen ke čtení (main); výstup agenta zde nelze uložit
  "node": { "id", "name", "kind", "purpose", "path": [ancestor names], "depth": children count, "sourceRef" },
  "goal": { "goal", "nonGoals", "acceptance" },            // ze spec uzlu (prázdné řetězce, když chybí)
  "content": { "text", "revision" } | null,               // text karty (node-text): podklad, typicky doslovný výňatek zadání; prázdný = null
  "definitionOfDone": { "acceptance", "criteria": [{id,text,checked}], "blockConditions": [{blockId, number, condition}] },
  "boundaries": { "nodeRules": [{id,text,kind}], "projectRules": [{id,text,kind,scope,target}], "nonGoals" },
  "context": { "materials": [{id,kind,path,caption,url}], "decisions": [...], "incomingReports": [edge report + from], "comments": [{id,title,text}], // lístky na stejné vrstvě jako karta, lidská poznámka pro orientaci, ne příkaz
    "area": {id,name,purpose} | null, // oblast, do které karta geometricky patří
    "knowledgeGraph": {...}, // mapa kódu z Graphify; cesty jsou reference, obsah se nečte
    "roleMemory": {status, role, items} },  // paměť role (OpenViking), viz pamet-agentu.md
  "harness": { "phase", "actions": [{index,id,pipelineId,label,params}], "steps": [...], "stopConditions": [texty] },
  "blocks": [ { id, number, title, text, tags, todos, images, state:{status,condition,onMet,onUnmet}, ports:[{id,label, edges:[{edgeId,targetId,targetName}]}] } ],
  "graph": { "incoming": [{edgeId, from, fromName, to, toName, port, sourceBlockId?, report?, agentWorkspace}], "outgoing": [...same...], "children": [{id,name,kind,agentWorkspace}], "parent": {id,name,kind,goal,rules,agentWorkspace} | null, // rodičovský rámec
    "innerComments": [{id,title,text}], // lístky na vrstvě uvnitř karty
    "areaFlows": [{edgeId,from,fromName,to,toName,direction: "in"|"out"}], // tok (port "flow"), který se dotýká oblasti karty
    "areaMembers": [{id,name,kind}] }, // ostatní karty ve stejné oblasti (bez komentářů a bez karty samotné)
  "loop": { "done", "openBlocks": n, "lastReport": nejnovější zpráva na odchozí vazbě nebo null },
  "agentWorkspace": {...},  // vlastní prostor modelu u karty: frame, log, failures, fixes, handoff
  "outputContract": {  // co má model vrátit, když skončí (viz agent-output)
    "schema": "opora.agent-output/1",
    "fields": { "blocks": "[{blockId, status: met|unmet|blocked, note}]", "reports": "[{edgeId, log, summary, handoff, improvements, errors}]", "done": "{proposed: bool, note}", "decisions": "[text]" },
    "jsonSchema": {...},  // JSON Schema výstupu
    "request": {project, workspace, nodeId, expectedRevision} | null,  // null v readOnly
    "transport": {format: "json-object", markdownFences: false, outputField: "output", agentField: "caller-supplied"},
    "reportScope": "outgoing-only"  // zprávy jen na odchozí vazby
  },
  "communication": { "incoming", "outgoing", "endpoints", "identityVerified": false },  // stránky zpráv, viz Adresovaná komunikace
  "orientation": {...}  // pořadí čtení pro nového agenta, viz Adresovaná komunikace
}
```
Fáze karty (`harness.phase`): postup existující karty do pozdější fáze vyžaduje neprázdná a všechna splněná kritéria (`definitionOfDone.criteria`), návrat je vždy volný. Nová karta smí vzniknout v libovolné fázi; brána kritérií platí jen pro postup existující karty.

`stopConditions` se odvozují z nesplněných podmínek bloků, pravidel `must_not` a uzavření karty. Samotný prázdný seznam podkladů práci neblokuje; povinný podklad musí být pojmenován v podmínce bloku. Orientace uvádí nepřipojené podklady jako volitelný kontext. Nový úkol nepotřebuje předávku předchozího agenta; chybějící předávka se hlásí při doloženém pokračování práce.

### Předání konkrétní verze zadání

Aktuální `node-brief` obsahuje `contextVersion` a `specification` (`opora.specification-context/1`): uložený projektový rámec, zadání karty a souvisejících karet, zděděné podmínky, sémantický graf a lokálně uložené podklady podle dostupnosti. `contextVersion` je otisk tohoto snímku. Pouhý posun karty při zachovaném členství v oblasti a hlášení postupu nejsou novou verzí zadání; změna jeho obsahu ano. Odkazy na externí soubory zůstávají referencemi, nikoli důkazem přečteného nebo archivovaného obsahu.

Aplikace a stránky jsou stejné uzly tohoto grafu, označené nepovinným `site`: aplikace nese prostředí s hosty, stránka cestu. `node.site` a metadata předků v `context.ancestors` orientují agenta, kam stránka a její komponenty patří. `specification.graph` uchovává stejná metadata; změna hostu nebo cesty mění `contextVersion` a nový OporaHub snímek je zachytí. Host není důkazem nasazení. Dlouhodobý účel se čte z `node.purpose`, pracovní zadání z `goal`; vytvoření stránky samo o sobě nevyplňuje cíl ani akceptaci úkolu.

Mapa domény ukládá pořadí stránek v pořadí uzlů grafu. Je-li v projektu stránka, `specification.navigation` přenáší seznam domén a jejich stránky v tomto pořadí (`nodeId`, `parentPageId`); obyčejné mezilehlé kontejnery nejsou dalšími stránkami. Změna pořadí stránek mění `contextVersion`, pouhé přerovnání běžných karet ne. Nové domény používají vlastní application ID a samostatné stromy; původní vícehostová aplikace stále znamená jednu sdílenou strukturu, nikoli prokázané oddělení prostředí.

Nové předání z UI kopíruje/stahuje celý brief. Požadavek v `outputContract.request` obsahuje vedle `expectedRevision` také `contextVersion`; obě hodnoty musí výsledek zachovat. Při změně zadání server odmítne zápis a rozepsaný výsledek se nesmí automaticky převázat na novou verzi.

Přijatý výsledek vrací `acceptedResult`. `GET /api/desktop-v3/agent-results?project&workspace&nodeId&before` a `node-brief.resultHistory` poskytují neměnnou evidenci s původním snímkem, verzí a úplným výstupem. Evidence a změna pracovního stavu se zapisují atomicky. Starší klient bez `contextVersion` zůstává kompatibilní, ale jeho záznam je výslovně `legacy-unbound`. Přijetí výsledku neznamená nezávislé ověření testů ani Git merge.

Nový commit OporaHubu ukládá tentýž serverem sestavený snímek do `specificationSnapshot`. Úplný historický obsah lze načíst přes `GET /api/opora-commit?project&workspace&scope&id`; server ověřuje rozsah i obsahový otisk. Staré commity bez snímku se nedoplňují domnělým historickým obsahem.

## Výstup modelu: `POST /api/desktop-v3/agent-output`
```
{ project, workspace, nodeId, expectedRevision, agent: string,
  output: { schema: "opora.agent-output/1", blocks: [...], reports: [...], done: {proposed, note}, decisions: [...] } }
```
Server pod zámkem a s CAS revizí: nastaví `blocks[].state.status`, zapíše `state.edges[edgeId]` (`by: "agent"`), u `done` nastaví `by: "agent", confirmed: false, note`, rozhodnutí přidá do `decisions` s `by: "agent"`. `blocks[].note` se nekopíruje do stavu karty, ale zachová se v úplném neměnném záznamu výsledku; předávka sousedovi patří do zprávy na vazbě (`reports`). Neznámý `blockId`/`edgeId` = chyba 409, nic se nezapíše. Uzavřená karta (`done.confirmed`) výstup odmítne. Vrací nový `StateResponse` doplněný o `acceptedResult`.

## Adresný blok: `GET/POST /api/desktop-v3/block`

Agent, který potřebuje sáhnout na jeden konkrétní blok (ne přečíst/přepsat celou kartu), použije adresný přístup místo `state`/`agent-output`.

### Čtení: `GET /api/desktop-v3/block?project&workspace&nodeId&blockId`
```
{ "revision", "node": {"id", "name"}, "block": Block, "children": [Block (přímé děti, seřazené podle čísla)], "parent": Block | null }
```
Neznámý `nodeId` nebo `blockId` v tomto rozsahu (i main, který je read-only) vrací **404**.

### Zápis: `POST /api/desktop-v3/block`
```
{ project, workspace, nodeId, expectedRevision, op }
```
`op.kind` je jedna ze čtyř operací, vždy nad bloky jedné karty (`nodeId`):

| kind | pole | co udělá |
|---|---|---|
| `add` | `parentBlockId` (`""` = kořen), `title`, `text` | přidá blok se stejnými výchozími hodnotami jako `emptyBlock` v `tree-model.ts` (`tags: []`, `todos: []`, `images: []`, `ports: []`, `state: {status:"open", condition:"", onMet/onUnmet: {kind:"none"}}`) |
| `update` | `blockId`, `patch: {title?, text?, tags?, state?, ports?}` | přepíše jen uvedené klíče; jiný klíč v `patch` je chyba |
| `remove` | `blockId` | smaže blok a celý podstrom; větve (`onMet`/`onUnmet`) ostatních bloků, které mířily na smazané bloky, se vyprázdní |
| `todo` | `blockId`, `todo: {kind: add\|toggle\|remove, id?, text?, assignee?}` | přidá/přepne/smaže jeden úkol bloku |

Po operaci se bloky karty přečíslují stejně jako `renumber` v `tree-model.ts` (kořen 1, 2, 3; děti 1.1, 1.2; pořadí sourozenců = pořadí uložení). Server pracuje pod zámkem grafu a s CAS na `expectedRevision` (409 při neshodě), uzavřená karta (`done.confirmed`) zápis odmítne (409), neznámý `nodeId`/`blockId` nic nezapíše (409), špatně tvarovaný požadavek je 409 (stejný mechanismus jako u `agent-output`). Validuje se výsledný stav (`validate_state`) a ukládá stejnou cestou jako `agent-output` (`DesktopV3State.save`).

Odpověď je běžný `StateResponse` (`revision, state, readOnly`) doplněný o `"block"`: dotčený blok po přečíslování, nebo `null` u `remove`.

## Pracovní prostor agenta (`agent-workspace`)

Mezipaměť modelu u jedné karty (uzel, sektor i oblast): kam si vede rámec a směr práce, co dělá, co se nepovedlo, co se povedlo opravit a co předává dál. Člověk ji vidí v inspektoru (Texty → Agenti; u sektoru a oblasti pod poli inspektoru) a smí do ní psát, ale je to prostor modelu, ne zadání. Nic v něm není příkaz.

Uloženo per `project + workspace + nodeId`, revizované jako text uzlu (`revision`, `savedAt`). Pět pojmenovaných sekcí, každá volný text do 12 000 znaků:

```
{
  frame: string     // rámec a směr: co je cílem této práce a kudy k němu jít
  log: string       // pracovní postup, krok po kroku
  failures: string  // co se nepovedlo a proč, aby to další agent neopakoval
  fixes: string     // úspěšné opravy: co se pokazilo a čím se to spravilo
  handoff: string   // předávka: kde pokračovat, co je rozdělané, na co navázat
  updatedAt: string // ISO
  by: "human" | "agent"
}
```

Čtení: `GET /api/desktop-v3/agent-workspace?project&workspace&nodeId` → `{ revision, workspace: {…výše…}, readOnly }`. Prázdný prostor má `revision: 0` a prázdné řetězce.

Zápis: `POST /api/desktop-v3/agent-workspace` s `{ project, workspace, nodeId, expectedRevision, sections: { frame?, log?, failures?, fixes?, handoff? }, by }`. Uvedené sekce se přepíší, neuvedené zůstanou. Neshoda `expectedRevision` = 409, nic se nezapíše. Neznámý klíč v `sections`, jiná hodnota `by` nebo překročená délka = 409. Uzavřená karta (`done.confirmed`) zápis odmítne (409). Smazání karty smaže i její pracovní prostor.

### Fraktální předávka

Karta je stejná na každé úrovni: sektor, uzel i oblast mají svůj prostor a předávka teče po vazbách i po hierarchii. Balíček `node-brief` proto nese:

- `agentWorkspace`: celý prostor karty samotné.
- `graph.incoming[].agentWorkspace`, `graph.outgoing[].agentWorkspace`: prostor karty na druhé straně každé vazby (i vazby z bloku, i toku mezi oblastmi). Když se propojí blok nebo karta, agent vidí předávku souseda.
- `graph.children[].agentWorkspace`: prostor každého potomka (jen `frame` a `handoff`, ostatní sekce si agent dočte odkazem), aby sektor byl souhrnem toho, co je v jeho uzlech.
- `graph.parent`: `{id, name, kind, goal: {goal, nonGoals, acceptance}, rules: [{id,text,kind}], agentWorkspace: {frame, handoff}}` nebo `null`, aby uzel znal cíl, pravidla i rámec sektoru, ve kterém stojí. `goal` je rodičova spec (`node_specs`), `rules` rodičovo `boundaries.nodeRules` — obojí prázdné (`""`, `[]`), když rodič nic nemá.
- `graph.areaMembers[].agentWorkspace`: `frame` a `handoff` karet ve stejné oblasti.

Předávka (`handoff`) má být seznam konkrétních kroků: kam se podívat, který soused nebo potomek nese souvislost a kudy podle vazeb a toku dat pokračovat. Odkaz na sekci má tvar `opora://agent-workspace/<nodeId>#<sekce>`; model ho používá ve zprávě na vazbě i ve vlastním prostoru místo kopírování textu.

### Co agent v balíčku má pro samostatnou práci

Balíček je úplný pracovní rámec, ne jen text: `goal` a `definitionOfDone` (kritéria, podle kterých pozná úspěšný konec), `boundaries` (pravidla must / must_not), `context` (podklady, rozhodnutí, příchozí zprávy, komentáře, oblast), `harness` (akce s pipeline a parametry, kroky, stop podmínky), `graph` (návaznosti a předávky výše), `loop` (stav smyčky: uzavření, otevřené bloky, poslední zpráva) a `agentWorkspace` (vlastní paměť a učení). K tomu `context.knowledgeGraph`: `{ available: bool, report: "graphify-out/GRAPH_REPORT.md", graph: "graphify-out/graph.json" }` podle toho, zda projekt má vygenerovanou mapu graphify; agent z ní čerpá souvislosti v kódu, které v kartách nejsou.

## Co je pevné a co se hýbe
Přetahovat po plátně jde hlavní karty (uzel, sektor, komentář), oblasti a boční bloky Akce / Pravidla / Podklady. Blok si drží posun vůči své kartě (`blockOffsets` uzlu v grafu), takže s kartou jede; porty, tlačítka bloků a vazby jsou napevno. Karty a oblasti jsou pevná tělesa: nepřekrývají se a karta je buď celá v oblasti, nebo celá mimo ni.
Pracovní prostor agenta je vázaný na kartu a její revizi; nikdy se nekopíruje mezi kartami, jen se na něj odkazuje.

## Adresovaná komunikace — první implementační řez v1

Rozšíření plánu: `.hermes/plans/2026-09-16_092217-agent-communication-workspace.md`. Přesný kontrakt prvního řezu: `.hermes/communication-v1/SPEC.md`; schéma zprávy: `shared/agent-message.schema.json`. Tento řez nenahrazuje pět textových sekcí a neimplementuje celý dlouhodobý plán.

- `GET /api/desktop-v3/agent-messages?project&workspace&nodeId&direction=incoming|outgoing&before` vrací zprávy adresované kartě nebo odeslané kartou. Nejnovější první, stránka 30, `hasMore` a exkluzivní `nextBefore`. `before` je nepovinné kladné serverové pořadí.
- `POST /api/desktop-v3/agent-messages`: `project, workspace, sourceNodeId, targetNodeId, kind, body, replyToMessageId, idempotencyKey, senderLabel`.
- Typy: `handoff`, `question`, `answer`, `blocker`, `result`, `correction`. Odpověď odkazuje na zprávu téže dvojice karet v témže projektu/workspace. Odeslaný obsah je neměnný.
- Stejný idempotency klíč a stejný obsah vrací tutéž zprávu; změněný obsah pod stejným klíčem je konflikt. Potvrzení HTTP samo není potvrzením převzetí práce.
- `POST /api/desktop-v3/agent-message-receipt`: `project, workspace, nodeId, messageId, digest, disposition, note, recipientLabel`. `nodeId` je příjemce a `digest` přesná SHA-256 verze zprávy.
- Rozhodnutí příjemce: `accepted`, `rejected`, `needs_clarification`; odmítnutí/upřesnění vyžaduje důvod. Tato verze ukládá jedno neměnné potvrzení na zprávu, opakování stejného je idempotentní. Upřesnění a nové rozhodnutí se vážou na novou navazující zprávu, nikoli přepsání starého potvrzení.
- Nový zápis do mainu nebo uzavřené karty není povolen. Přesné opakování již uloženého potvrzení na mezitím uzavřené kartě pouze vrátí původní záznam; nic nevytváří ani nepřepisuje. Jiný obsah potvrzení, chybný digest či jiný příjemce se odmítá. Scope se ověřuje proti skutečným kartám; text zprávy neuděluje právo číst soubory, změnit projekt ani spustit proces.
- `senderLabel` a `recipientLabel` jsou deklarované popisky. **`identityVerified: false` je záměrné a musí být vidět i v UI.** Nejde o ověřenou identitu modelové session, autentizované předání vlastnictví nebo lidské schválení výsledku.
- Text → Agenti skládá stávající pracovní paměť a rozbalitelnou komunikaci Příchozí/Odchozí. Čtení je pasivní, převzetí je explicitní. Síťová chyba či konflikt nesmí smazat rozepsaný text.

Orientace nového agenta je nyní aditivně v `node-brief.orientation` a skutečné stránky zpráv v `node-brief.communication`. V Text → Agenti je zobrazuje Start pro nového agenta: pořadí čtení, zdroje, mezery, volitelný kontext, doporučený krok, hledání v načteném kontextu a kopie úplného JSON. Praktický vstupní návod je `docs/agent-onboarding.md`. Paměť, kterou read-only pohled nezpřístupňuje, je `unavailable`, nikoli údajně chybějící; GET nic nepotvrzuje ani nemění.

Samostatné kroky další implementace: vazba na ověřený runtime/scope, atomický převod vlastnictví, bohatší checkpointy a řízená obnova. Není dovoleno je vykazovat jako hotové jen proto, že funguje zpráva a receipt. Důkazy komunikace jsou v `.hermes/communication-v1/`, orientace a jejího nasazení v `.hermes/agent-orientation-v1/`. Vizuální průchod se ověřuje odděleně od testů a HTTP.

## Pipeline karty (port „pipeline“)

Proces karty je autonomní. ROUTER (orchestrátor, LLM na začátku) určí každé kartě pipeline a každou
etapu dělá **vlastní nová relace** agenta (karta + jedna etapa), ne jedna dlouhá relace. Proto
proces drží server (`backend/editor/agent_memory/card_pipeline.py`, `pipeline_routing.py`).
Člověk jen sleduje a jedním klikem přepne profil (čipy v bloku Pipeline).

Stav uzlu `stages = {profile, items, routedBy, reason}`; etapa
`{id, kind: work|test|review|fix|critic, lens: ""|user|sly|hacker, title, brief, status, note, by, approved, doneBy, at, retryOf?}`.

**Router**
- `GET /api/desktop-v3/frontier`: `needsRouting` = otevřené karty bez pipeline; každý řádek karty nese
  `pipeline {routed, profile, current {id, kind, lens, title}, finished, total, stuck}`.
- `GET /api/desktop-v3/pipeline-profiles`: šablony profilů goal, code, design, security, testing, research, custom (jediný zdroj pravdy).
- `POST /api/desktop-v3/pipeline` `{project, workspace, nodeId, expectedRevision, op: route|add, reason, profile?, stages?[{kind, lens, title, brief}]}`.
  `route` sestaví pipeline ze šablony (+ etapy navíc), `add` vloží etapy za rozpracovanou část.

**Pravomoci (aditivní = autonomní, ubírající = člověk)**
- Agent etapy přidává kdykoli (platí hned). Profil přestaví, jen dokud je vše `todo` a pipeline nesestavil člověk.
- Odebrat, přeskládat, upravit definici a přeskočit (`skipped`) smí jen člověk (agent 403, i přes `/state`).
- Podlaha pipeline od routeru: `review` + kritik `hacker`; karta `[task]` nebo s `checks` i `test`. Jinak 409 s výčtem.

**Relace na etapě**: `frontier` → lease claim → `node-brief` (`pipeline.current`, předávky = `note` předchozích etap)
→ práce → `agent-output.output.stages [{id, status: doing|passed|failed, note}]` → release.
- `passed`/`failed` nese neprázdné `note` (předávka další relaci).
- Pořadí: etapu lze nahlásit, až když předchozí byly zkusené (ne `todo`/`doing`). Kritici, kteří jdou po sobě,
  tvoří kolo: odevzdávají se v libovolném pořadí (paralelně, `pipeline.parallel`), jakmile jsou uzavřené etapy před kolem.
- Blokátor vs. podnět: `review` a `critic` dají `failed` JEN pro blokátor (rozbije MVP nebo proces aplikace, ztráta
  či únik dat, bezpečnost, regrese běžného vstupu proti předchozímu chování); vše ostatní = `passed` + podnět
  v `agent-output.output.ideas [{text, source}]` (stav uzlu `ideas`, viz níže).
- Nezávislost: `review` a `critic` neuzavře relace (jméno agenta), která uzavřela `work`/`fix`.
- GOAL: `test` na kartě `goal_mode: until_checks_pass` projde jen se zelenými `evidence.checksRun`.
- Selhaný `test`/`review`/`critic` sám vloží `fix` a opakování (`retryOf`); selže-li v jednom kole víc kritiků,
  vznikne jedna společná oprava za kolem a opakování každého z nich. Po 2 smyčkách pipeline čeká na člověka
  (`pipeline.stuck`, `loop.waitingOnHuman`, frontier `waiting`).
- Uzavření karty (člověk i autonomie) jen když je každá etapa `passed`, člověkem `skipped`, nebo ji nahradilo úspěšné opakování.

**Podněty k dalšímu vývoji** (`backend/editor/agent_memory/card_ideas.py`): stav uzlu
`ideas = [{id, text, by, source: human|agent|review|work|test|fix|critic:user|sly|hacker, stageId?, at, status: open|done}]`.
Agent je přidává jen přes `agent-output.output.ideas` (nejvýš 20 na výstup, text do 1000 znaků, bez duplicit podle
textu, nejvýš 200 na kartě; `stageId` = etapa uzavřená stejným výstupem). `node-brief.ideas` = `{open, done, policy}`.
Odškrtnout (`done`) a smazat smí jen člověk (detail karty, záložka Podněty); obecný zápis stavu od agenta 403.

**Kola karty** (`backend/editor/agent_memory/card_rounds.py`): uzavřenou kartu otevře jako nové kolo jen člověk
(`POST /api/desktop-v3/card-round {project, workspace, nodeId, expectedRevision, reason}`; agent 403, neznámý 428).
Kolo N se zamrazí do append-only `card_rounds` (`opora.card-round/1`: zadání kola s doslovnými revizemi fragmentů,
pipeline s předávkami, bloky, důkazy, commity, nálezy kritiků, chyby, Podněty, předávky, prostor agenta, odkazy na
výsledky agentů); `GET /api/desktop-v3/card-rounds?nodeId=&round=` je čte. Karta v kole N+1: bez pipeline (router),
fáze `discover` (zamrazená fáze kola je v záznamu `phase`), bloky `open`, důkazy `pending`, jen otevřené Podněty, prázdný prostor agenta, `fragmentRefs` na aktuální revize,
porty bloků bez volby (`status`/`reason`) a kritéria nezaškrtnutá (nové zadání = nové postupy; volby zůstávají v zamrazeném
kole a `previousRounds[].decided` = „rozhodnutí v1: …“ jako kontext), rozhodnutí karty se nemažou a v node-brief nesou
`context.decisions[].fromRound` (UI Paměť projektu: štítek „z v1“), stav uzlu `round = {number, openedAt, by, reason}` (obecný zápis stavu ho nemění). `node-brief.rounds` = aktuální
kolo a jeho doslovné zadání (`rounds.brief.fragments`, zamrazená kopie; nemění se se schránkou; text schránky je `trust.dataFromAgents`), `node-brief.previousRounds`
= kompaktní shrnutí každého kola (postup, chyby, nálezy, commity, Podněty, `detail`): poznámka etapy jen jednou
(`pipeline.stages[].note`, zkrácená na 280 znaků), `criticFindings[].stageId` a `errors.failedStageIds` na ni odkazují;
plné texty v `detail`. Verze plátna nesou kola (část `cardRounds`).

## Kontrolní pás karty

Deset polí ano / ne: `goal, done, text, blocks, links, source, checks, pipeline, evidence, handoff`, stav
`yes` (je) / `no` (chybí) / `run` (rozpracováno) / `fail` (selhalo nebo čeká na člověka) a `hint` (co doplnit a kam).
Jeden výpočet (`backend/editor/agent_packet/card_checklist.py`) pro plátno (pás pod hlavičkou karty, souhrn
oblasti), `GET /api/desktop-v3/card-checklist?layer=`, `node-brief.checklist` a `frontier` (`missing` = klíče,
které nejsou `yes`). Relace začne tím, co chybí, a na konci ověří, že po jejím výstupu pole zezelenala.
Obálka na vazbě mezi kartami ukazuje předávku: „předáno“ = `state.edges[id].handoff`, „chybí“ = zdroj je hotový bez zprávy.

