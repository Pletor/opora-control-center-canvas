// Trvalý štítek „Plná autonomie agentů“: dokud je v projektu zapnutá, vidí ho člověk v hlavičce projektu
// i ve velínu. Dostává hotový stav od rodiče; při vypnuté autonomii nekreslí nic.
import Icon from "@/ui-kit/icon/components/Icon";
import { autonomyTitle, type AgentAutonomy } from "../logic/agent-autonomy";
import "../styles/agent-autonomy.css";

export default function AgentAutonomyBadge({ autonomy, place = "header" }: {
  autonomy: AgentAutonomy;
  /** Kde štítek stojí: v liště/hlavičce projektu je kompaktní, ve velínu o stupeň větší. */
  place?: "header" | "velin";
}) {
  if (!autonomy.full) return null;
  return (
    <span className={`agent-autonomy-badge agent-autonomy-badge--${place}`} role="status"
      data-testid="agent-autonomy-badge" title={autonomyTitle(autonomy)}>
      <Icon name="bot" size={16} />Plná autonomie agentů
    </span>
  );
}
