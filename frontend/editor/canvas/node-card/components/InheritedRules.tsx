import type { EffectiveRule } from "../logic/effective-rules";
import { AGENT_RULE_LABEL, isAgentRule } from "@/shared/desktop-state/logic/agent-rule";

const labels = { project: "Projekt", path: "Cesta", sector: "Sektor", card: "Karta" };
const icons = { project: "◉", path: "↳", sector: "▦", card: "▣" };

export default function InheritedRules({ rules }: { rules: (EffectiveRule & { by?: "human" | "agent" })[] }) {
  return <div className="node-card__rules nodrag" onClick={(event) => event.stopPropagation()}>
    {rules.map((rule) => {
      const source = `${labels[rule.origin.scope]}: ${rule.origin.name || rule.origin.path || "celý projekt"}`;
      const proposal = isAgentRule(rule);
      const title = `${source}${proposal ? ` · 🤖 ${AGENT_RULE_LABEL}` : ""} · ${rule.text}`;
      return <details key={`${rule.origin.storage}:${rule.origin.nodeId}:${rule.id}`} className={proposal ? "node-card__fold--proposal" : undefined}>
        <summary title={title} aria-label={title}>
          {proposal && "🤖 "}{icons[rule.origin.scope]} {rule.kind === "must_not" ? "⊘" : "✓"}
        </summary>
        <small>{source}{rule.inherited ? " · zděděné" : ""}{proposal ? ` · 🤖 ${AGENT_RULE_LABEL}` : ""}</small>
        <p>{rule.text}</p>
      </details>;
    })}
  </div>;
}
