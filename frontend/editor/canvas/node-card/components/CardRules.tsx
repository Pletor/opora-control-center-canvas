import { useState } from "react";
import type { Rule } from "@/shared/desktop-state/logic/types";
import MemoryItemText from "@/editor/llm-control/project-memory/components/MemoryItemText";
import { AGENT_RULE_LABEL, asHumanRule, isAgentRule } from "../logic/agent-rule";

export default function CardRules({ rules, disabled, write }: {
  rules: Rule[]; disabled: boolean; write: (expected: Rule, item: Rule) => Promise<boolean>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  // Uložení člověkem pravidlo vždy schválí: odešle se bez `by`, takže návrh agenta začne platit.
  async function save(rule: Rule, text: string) {
    setBusy(true); setError("");
    try {
      const saved = await write(rule, asHumanRule(rule, text));
      if (!saved) setError("Pravidlo se nepodařilo uložit. Obnovte kartu a porovnejte změny.");
      return saved;
    } finally { setBusy(false); }
  }
  return <div className="node-card__rules nodrag" onClick={(event) => event.stopPropagation()}>
    {rules.map((rule) => {
      const proposal = isAgentRule(rule);
      const label = `${rule.kind === "must" ? "Pravidlo" : "Zákaz"}${proposal ? ` (${AGENT_RULE_LABEL})` : ""}: ${rule.text}`;
      return <details key={rule.id} style={proposal ? { opacity: 0.6, fontStyle: "italic" } : undefined}>
        <summary title={proposal ? `🤖 ${AGENT_RULE_LABEL} · ${rule.text}` : rule.text} aria-label={label}>
          {proposal && "🤖 "}{rule.kind === "must" ? "✓" : "⊘"}
        </summary>
        {proposal && <small style={{ display: "block" }}>🤖 {AGENT_RULE_LABEL}</small>}
        <MemoryItemText id={`canvas-rule:${rule.id}`} text={rule.text} disabled={disabled || busy}
          save={(text) => save(rule, text)} />
        {proposal && <button type="button" disabled={disabled || busy} title="Uložit pravidlo jako člověk; pak platí i pro agenty"
          onClick={() => void save(rule, rule.text)}>✓ Schválit</button>}
      </details>;
    })}
    {error && <span role="alert">{error}</span>}
  </div>;
}
