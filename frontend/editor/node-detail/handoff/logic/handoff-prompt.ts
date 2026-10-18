// Zadání „Předat agentovi“: jeden text ke zkopírování do terminálu se skillem `/opora-control-center`,
// který dnes člověk skládá ručně podle `docs/postup-vyvoje-projektu.md` §2. Čistá funkce bez Reactu.
// Do instrukčních vět jdou jen ověřené identifikátory (projekt, workspace, karta, id etapy); název karty
// a název etapy stojí jen v datovém bloku. Etapu agent stejně ověří z aktuálního briefu.
import { dataBlock, oneLine, safeIds } from "@/shared/agent-prompt/logic/agent-prompt";
import { pipelineSummary, type CardPipeline, type PipelineStage } from "@/editor/workflow/card-pipeline/logic/pipeline-model";

/** Etapa pipeline na řadě, jak ji zadání potřebuje: id a druh do instrukce, název jen do dat. */
export type HandoffStage = Pick<PipelineStage, "id" | "kind" | "title">;

export type HandoffInput = {
  project: string;
  workspace: string;
  nodeId: string;
  name: string;
  /** Etapa na řadě (`handoffStage`), nebo `null`, když karta pipeline nemá nebo je vyřešená. */
  stage?: HandoffStage | null;
};

/** Etapa pipeline, která je na řadě (`pipelineSummary().current`); `null` bez pipeline nebo po jejím vyřešení. */
export function handoffStage(pipeline: CardPipeline | undefined): HandoffStage | null {
  if (!pipeline) return null;
  const current = pipelineSummary(pipeline).current;
  return current ? { id: current.id, kind: current.kind, title: current.title } : null;
}

/** Hotové zadání pro agenta, který převezme kartu; `null`, když identifikátor (i id či druh etapy) neprojde. */
export function handoffPrompt({ project, workspace, nodeId, name, stage = null }: HandoffInput): string | null {
  if (!safeIds(project, workspace, nodeId)) return null;
  if (stage && !safeIds(stage.id, stage.kind)) return null;
  return [
    "/opora-control-center",
    `Projekt ${project}, workspace ${workspace}, karta id ${nodeId}.`,
    ...dataBlock("Karta", [
      `Název karty: ${oneLine(name)}`,
      ...(stage ? [`Etapa na řadě: ${oneLine(stage.title || stage.kind)}`] : []),
    ]),
    "Postupuj podle references/agent-loop.md: frontier → lease claim → node-brief --raw → práce podle pravidel repa (CLAUDE.md) a rozsahu karty → agent-output (bloky, stages, evidence, předávka) → lease release.",
    ...(stage ? [`Na řadě je etapa s id ${stage.id} (${stage.kind}); ověř ji z aktuálního briefu (\`pipeline.current\`) a hlaš výsledek jen k ní.`] : []),
    `Commity s trailerem \`Opora-Node: ${nodeId}@<revize zadání>\`. Nepushuj.`,
  ].join("\n");
}
