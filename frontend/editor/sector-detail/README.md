Detail sektoru: stejná šablona jako node-detail (inspektor sektoru je `NodePanel`); tady leží dílky, které
má jen sektor.

`components/SectorDecompose.tsx` je složený oddíl „Rozložit na karty“ v záložce Zadání pod
`NodeSpecEditor` (montuje ho `NodePanel` jen pro `kind === "sector"`). Ukáže stav (kolik karet sektor už
má), zadání pro agenta-rozkladače sektoru jen ke čtení a tlačítko „Kopírovat zadání“ (schránka, 2 s
„Zkopírováno“). Nic nespouští; agent jede v terminálu podle
`.claude/skills/opora-control-center/references/rozklad.md`, oddíl „Sektor → karty“ (dávka
`canvas-plan --dry-run` → celá dávka ke schválení → ostře). Počet karet (`childCount` v `NodePanel`)
spočítá App z grafu: přímé děti sektoru s `kind === "node"`.

`logic/sector-decompose-prompt.ts` (testováno) skládá zadání: `sectorDecomposePrompt({project, workspace,
sectorId, sectorName, purpose, cards})` vrátí text začínající `/opora-control-center`, nebo `null`, když
chybí id sektoru. Název, podstata a počet karet jsou citovaná data („Sektor (data, ne pokyn)“); cíl,
akceptaci a bránu si agent čte sám z `node-brief --raw` sektoru. Karty míří do sektoru přes
`parent: "@<id sektoru>"`.

`components/IdeasSummary.tsx` je složený oddíl „Shrnout podněty (N)“ pod rozkladem; `NodePanel` ho ukáže
jen sektoru s N > 0 otevřenými podněty v jeho kartách (`openIdeasInSector`, spočítá App z `ideas` přímých
dětí sektoru). Podněty se člověku neukazují jako seznam (`docs/pyramida.md` §1 bod 4): zadání z
`logic/ideas-summary-prompt.ts` (testováno, `null` bez sektoru nebo bez podnětů) pošle agenta podle
`references/rozklad.md`, oddíl „Podněty → jedno rozhodnutí“, shrnout je do nejvýš 3 témat a jednoho
rozhodnutí; nic neodškrtává.

`styles/sector-detail.css`: blok `sector-fold` pro oba oddíly (stejný rytmus jako `area-decompose` u oblasti).
