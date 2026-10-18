Předání karty agentovi: zadání ke zkopírování místo ručně psaného promptu z
`docs/postup-vyvoje-projektu.md` §2.

`components/CardHandoff.tsx` je složený oddíl „Předat agentovi“ v záložce Zadání pod `NodeSpecEditor`
(montuje ho `NodePanel` jen pro `kind === "node"`). Ukáže větu o etapě na řadě (nebo krátkou nápovědu),
zadání jen ke čtení a tlačítko „Kopírovat zadání“ (schránka, 2 s „Zkopírováno“). Nic nespouští ani
neukládá.

`logic/handoff-prompt.ts` (testováno): `handoffPrompt({project, workspace, nodeId, name, stage})` vrátí
text začínající `/opora-control-center` (smyčka podle `references/agent-loop.md`, trailer
`Opora-Node: <id>@<revize zadání>`, „Nepushuj.“), nebo `null`, když projekt, workspace, id karty nebo
id/druh etapy neprojde `PROMPT_ID`. Název karty a název etapy stojí jen v datovém bloku
(`frontend/shared/agent-prompt`); instrukce jmenuje etapu jen id a druhem („Na řadě je etapa s id … (…);
ověř ji z aktuálního briefu“). `handoffStage(pipeline)` vrátí etapu z `pipelineSummary().current`, nebo
`null`; volá ji App a výsledek předá do `NodePanel` jako `stageOnTurn`. Kopírování a hlášky (`role="status"`
/ `role="alert"`) dělá sdílený `frontend/shared/hooks/logic/use-copy-text.ts`.

`styles/handoff.css`: blok `card-handoff`.
