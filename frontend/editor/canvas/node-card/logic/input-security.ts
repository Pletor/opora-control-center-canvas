import { nodeWorkflowOf, type DesktopState } from "@/shared/desktop-state/logic/types";
import { emptyBlock, renumber } from "@/editor/node-detail/tree/logic/tree-model";

export const setUrlDownload = (nodeId: string, enabled: boolean) => (state: DesktopState): DesktopState => {
  const node = nodeWorkflowOf(state, nodeId);
  let blocks = node.blocks;
  if (enabled && !blocks.some(block => block.tags.includes("input-security"))) {
    const text = "Ověřit povolené URL, SSRF a privátní adresy, DNS a přesměrování, limity velikosti/času a typ obsahu; doložit testy.";
    const block = emptyBlock();
    blocks = renumber([...blocks, { ...block, title: "Bezpečnost vstupu", text, tags: ["input-security"], state: { ...block.state, condition: text } }]);
  }
  return { ...state, nodes: { ...state.nodes, [nodeId]: { ...node, downloadsUrl: enabled, blocks } } };
};
