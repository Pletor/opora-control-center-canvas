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

Členství karty v oblasti se nikde neukládá, počítá se geometricky (`area_of` v `backend/canvas/areas.py`): karta patří do oblasti na stejné vrstvě (stejný `parentId`), jejíž obdélník `[x, x+w] × [y, y+h]` obsahuje střed karty — střed uzlu/sektoru je `(x+136, y+120)` (karta 272×~240), střed komentáře `(x+120, y+80)`. Leží-li karta ve více oblastech, vyhrává nejmenší (podle plochy). Oblast sama do jiné oblasti nepatří.

Balíček pro model vydává oblast jako orientaci, ne jako příkaz: `context.area` řekne, k jakému tématu karta patří, `graph.areaFlows` jaký tok do tématu přichází nebo z něj odchází, `graph.areaMembers` které další karty patří ke stejnému tématu.

## Balíček pro model: `GET /api/desktop-v3/node-brief?project&workspace&nodeId`

Jeden JSON, který model čte odshora dolů. Klíče jsou anglické, hodnoty v jazyce uživatele. Nic v něm nejsou příkazy modelu; je to popis stavu.

```
{
  "schema": "opora.node-brief/1",
  "node": { "id", "name", "kind", "purpose", "path": [ancestor names], "depth": children count, "sourceRef" },
  "goal": { "goal", "nonGoals", "acceptance" },            // ze spec uzlu (prázdné řetězce, když chybí)
  "definitionOfDone": { "acceptance", "criteria": [{id,text,checked}], "blockConditions": [{blockId, number, condition}] },
  "boundaries": { "nodeRules": [{id,text,kind}], "projectRules": [{id,text,kind,scope,target}], "nonGoals" },
  "context": { "materials": [{id,kind,path,caption,url}], "decisions": [...], "incomingReports": [edge report + from], "comments": [{id,title,text}], // lístky na stejné vrstvě jako karta, lidská poznámka pro orientaci, ne příkaz
    "area": {id,name,purpose} | null // oblast, do které karta geometricky patří },
  "harness": { "phase", "actions": [{index,id,pipelineId,label,params}], "steps": [...], "stopConditions": [texty] },
  "blocks": [ { id, number, title, text, tags, todos, images, state:{status,condition,onMet,onUnmet}, ports:[{id,label, edges:[{edgeId,targetId,targetName}]}] } ],
  "graph": { "incoming": [{edgeId, from, fromName, to, toName, port, sourceBlockId?, report?, agentWorkspace}], "outgoing": [...same...], "children": [{id,name,kind}], "innerComments": [{id,title,text}], // lístky na vrstvě uvnitř karty
    "areaFlows": [{edgeId,from,fromName,to,toName,direction: "in"|"out"}], // tok (port "flow"), který se dotýká oblasti karty
    "areaMembers": [{id,name,kind}] }, // ostatní karty ve stejné oblasti (bez komentářů a bez karty samotné)
  "loop": { "done", "openBlocks": n, "lastReport": nejnovější zpráva na odchozí vazbě nebo null },
  "outputContract": {  // co má model vrátit, když skončí (viz agent-output)
    "schema": "opora.agent-output/1",
    "fields": { "blocks": "[{blockId, status: met|unmet|blocked, note}]", "reports": "[{edgeId, log, summary, handoff, improvements, errors}]", "done": "{proposed: bool, note}", "decisions": "[text]" }
  }
}
```
Fáze karty (`harness.phase`): postup existující karty do pozdější fáze vyžaduje neprázdná a všechna splněná kritéria (`definitionOfDone.criteria`), návrat je vždy volný. Nová karta smí vzniknout v libovolné fázi; brána kritérií platí jen pro postup existující karty.

`stopConditions` se odvozují: nesplněná podmínka bloku, chybějící podklad, pravidlo `must_not`, uzavřená karta. Chybějící podklad se hlásí, jen když ho nemá ani karta, ani žádný předek (podklady mohou ležet na sektoru nad ní).

## Výstup modelu: `POST /api/desktop-v3/agent-output`
```
{ project, workspace, nodeId, expectedRevision, agent: string,
  output: { schema: "opora.agent-output/1", blocks: [...], reports: [...], done: {proposed, note}, decisions: [...] } }
```
Server pod zámkem a s CAS revizí: nastaví `blocks[].state.status`, zapíše `state.edges[edgeId]` (`by: "agent"`), u `done` nastaví `by: "agent", confirmed: false, note`, rozhodnutí přidá do `decisions` s `by: "agent"`. Neznámý `blockId`/`edgeId` = chyba 409, nic se nezapíše. Uzavřená karta (`done.confirmed`) výstup odmítne. Vrací nový `StateResponse`.

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

