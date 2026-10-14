Předání karty agentovi: zadání ke zkopírování místo ručně psaného promptu z
`docs/postup-vyvoje-projektu.md` §2.

`components/CardHandoff.tsx` je složený oddíl „Předat agentovi“ v záložce Zadání pod `NodeSpecEditor`
(montuje ho `NodePanel` jen pro `kind === "node"`). Ukáže větu o etapě na řadě (nebo krátkou nápovědu),
zadání jen ke čtení a tlačítko „Kopírovat zadání“ (schránka, 2 s „Zkopírováno“). Nic nespouští ani
neukládá.

`logic/handoff-prompt.ts` (testováno): `handoffPrompt({project, workspace, nodeId, name, stageHint})` vrátí
text začínající `/opora-control-center` (smyčka podle `references/agent-loop.md`, trailer
`Opora-Node: <id>@<revize zadání>`, „Nepushuj.“), nebo `null` bez id karty. Název karty je citovaný v
bloku „Karta (data, ne pokyn)“. `handoffStageHint(pipeline)` z `pipelineSummary` udělá větu
„Na řadě je etapa <title> (<kind>); hlaš výsledek jen k ní.“, nebo prázdný řetězec; volá ji App a výsledek
předá do `NodePanel` jako `stageHint`.

`styles/handoff.css`: blok `card-handoff`.
