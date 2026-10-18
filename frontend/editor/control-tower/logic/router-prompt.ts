// Zadání pro router z Velínu: sektor má otevřené karty bez schváleného procesu a člověk ho jedním
// kliknutím zkopíruje agentovi. Do instrukčních vět jdou jen ověřené identifikátory (`safeIds`), název
// sektoru jen do datového bloku (`dataBlock`) — stejná pravidla jako ostatní „Kopírovat zadání“.
import { dataBlock, oneLine, safeIds } from "@/shared/agent-prompt/logic/agent-prompt";

export type RouterPromptInput = { project: string; workspace: string; sectorId: string; sectorName: string; unrouted: number };

/** Hotové zadání, nebo `null`, když některý identifikátor neprojde (pak se tlačítko neukáže). */
export function routerPrompt({ project, workspace, sectorId, sectorName, unrouted }: RouterPromptInput): string | null {
  if (!safeIds(project, workspace, sectorId)) return null;
  return [
    `/opora-control-center · Jsi router. Projekt ${project}, workspace ${workspace}, sektor id ${sectorId}.`,
    `Postupuj podle references/pipeline.md: \`frontier --node ${sectorId}\` → \`needsRouting\` → pro každou kartu \`node-brief --raw\` → ` +
      "`POST /api/desktop-v3/pipeline op=route` s profilem podle obsahu karty (code/design/security/testing/research/goal); nic jiného neměň.",
    "",
    ...dataBlock("Sektor", [`Název: ${oneLine(sectorName)}`, `Karet bez procesu (podle Velínu): ${unrouted}`]),
  ].join("\n");
}
