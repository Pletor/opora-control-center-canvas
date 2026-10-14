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

`styles/sector-detail.css`: blok `sector-decompose` (stejný rytmus jako `area-decompose` u oblasti).
