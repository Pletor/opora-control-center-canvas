import { useState } from "react";
import type { Rule } from "@/shared/desktop-state/logic/types";
import MemoryItemText from "@/editor/llm-control/project-memory/components/MemoryItemText";
import RuleReview from "@/editor/llm-control/project-memory/components/RuleReview";
import { AGENT_RULE_LABEL, asHumanRule, isAgentRule, type RuleReviewDecision } from "@/shared/desktop-state/logic/agent-rule";

export default function CardRules({ rules, disabled, write, review }: {
  rules: Rule[]; disabled: boolean; write: (expected: Rule, item: Rule) => Promise<boolean>;
  review: (rule: Rule, decision: RuleReviewDecision) => Promise<boolean>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function run(action: () => Promise<boolean>) {
    setBusy(true); setError("");
    try {
      const saved = await action();
      if (!saved) setError("Pravidlo se nepodařilo uložit. Obnovte kartu a porovnejte změny.");
      return saved;
    } finally { setBusy(false); }
  }
  // Uložení člověkem pravidlo vždy schválí: odešle se bez `by`, takže návrh agenta začne platit.
  const save = (rule: Rule, text: string) => run(() => write(rule, asHumanRule(rule, text)));
  return <div className="node-card__rules nodrag" onClick={(event) => event.stopPropagation()}>
    {rules.map((rule) => {
      const proposal = isAgentRule(rule);
      const label = `${rule.kind === "must" ? "Pravidlo" : "Zákaz"}${proposal ? ` (${AGENT_RULE_LABEL})` : ""}: ${rule.text}`;
      return <details key={rule.id} style={proposal ? { opacity: 0.6, fontStyle: "italic" } : undefined}>
        <summary title={proposal ? `🤖 ${AGENT_RULE_LABEL} · ${rule.text}` : rule.text} aria-label={label}>
          {proposal && "🤖 "}{rule.kind === "must" ? "✓" : "⊘"}
        </summary>
        <MemoryItemText id={`canvas-rule:${rule.id}`} text={rule.text} disabled={disabled || busy}
          save={(text) => save(rule, text)} />
        <RuleReview rule={rule} disabled={disabled || busy} review={(item, decision) => void run(() => review(item, decision))} />
      </details>;
    })}
    {error && <span role="alert">{error}</span>}
  </div>;
}
