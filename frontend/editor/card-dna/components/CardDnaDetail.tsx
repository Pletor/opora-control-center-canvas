import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import type { DesktopState } from "@/shared/desktop-state/logic/types";
import type { NodeCardData } from "@/editor/canvas/node-card/components/NodeCard";
import type { CardDnaTab } from "./CardDnaDialog";
import CardDnaOverview from "./CardDnaOverview";
import CardDnaAssignment from "./CardDnaAssignment";
import CardDnaProcess from "./CardDnaProcess";
import CardDnaWorkflow from "./CardDnaWorkflow";
import CardDnaEvidence from "./CardDnaEvidence";
import CardDnaCode from "./CardDnaCode";
import CardDnaExport from "./CardDnaExport";

type Props = { tab: CardDnaTab; node: CanvasNode; data: NodeCardData; state: DesktopState; graph: Graph;
  project?: string; workspace?: string; onSaveNode?: (node: CanvasNode) => void; onTab: (tab: CardDnaTab) => void };
/** Rodič skládá právě jednu záložku; neaktivní editory ani jejich načítání neexistují. */
export default function CardDnaDetail(props: Props) {
  switch (props.tab) {
    case "overview": return <CardDnaOverview nodeId={props.node.id} {...props} />;
    case "spec": return <CardDnaAssignment {...props} />;
    case "process": return <CardDnaProcess {...props} />;
    case "workflow": return <CardDnaWorkflow {...props} />;
    case "evidence": return <CardDnaEvidence {...props} />;
    case "code": return <CardDnaCode {...props} />;
    case "dna": return <CardDnaExport {...props} />;
  }
}
