// Sekce Kontext: co model z tohoto uzlu dostane a co ještě chybí. Jen čtení; nic se neodesílá modelu.
// Balíček pro model se stahuje na vyžádání člověka (GET node-brief) a zobrazí se jako JSON ke zkopírování.
import { useState } from "react";
import type { CanvasNode, GraphEdge } from "@/shared/types/logic/types";
import type { NodeBrief, NodeWorkflowFull } from "@/shared/desktop-state/logic/types";
import { errorMessage, fetchNodeBrief } from "@/shared/desktop-state/logic/api";
import { contextChecks, contextScore } from "@/editor/component-library/node-library/logic/library-model";

export default function LibraryContext({
  node,
  workflow,
  edges,
  project,
  workspace,
}: {
  node: CanvasNode;
  workflow: NodeWorkflowFull;
  /** Vazby grafu: podle nich se pozná, zda z portu bloku někam vede cesta. */
  edges: GraphEdge[];
  project: string;
  workspace: string;
}) {
  const checks = contextChecks(node, workflow, edges);
  const score = contextScore(checks);
  const missing = <em className="node-library__missing">chybí</em>;
  const [brief, setBrief] = useState<NodeBrief | null>(null);
  const [briefError, setBriefError] = useState("");
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const text = brief ? JSON.stringify(brief, null, 2) : "";
  async function download() {
    setLoading(true);
    setBriefError("");
    setCopied(false);
    try {
      setBrief(await fetchNodeBrief(project, workspace, node.id));
    } catch (e) {
      setBrief(null);
      setBriefError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }
  return (
    <div className="node-library__context" data-testid="library-context">
      <p className="node-library__note">
        Model dostane přesně to, co je v kartě: cíl, bloky, pravidla, podklady a akce. Splněno <b>{score.done} / {score.total}</b>.
      </p>
      <ol className="node-library__checks">
        {checks.map((check) => (
          <li key={check.id} className={"node-library__check" + (check.ok ? " node-library__check--ok" : "")}>
            <span className="node-library__check-mark" aria-hidden="true">{check.ok ? "✓" : "·"}</span>
            <span className="node-library__pick-text"><strong>{check.label}</strong><small>{check.hint}</small></span>
          </li>
        ))}
      </ol>
      <h4 className="node-library__category-title">Co agent uvidí</h4>
      <dl className="node-library__summary">
        <dt className="node-library__summary-key">Cíl</dt><dd className="node-library__summary-value">{node.purpose.trim() || missing}</dd>
        <dt className="node-library__summary-key">Bloky</dt><dd className="node-library__summary-value">{workflow.blocks.length ? workflow.blocks.map((b) => `${b.number} ${b.title}`).join(" · ") : missing}</dd>
        <dt className="node-library__summary-key">Pravidla</dt><dd className="node-library__summary-value">{workflow.rules.length ? workflow.rules.map((r) => `${r.kind === "must" ? "musí" : "nesmí"}: ${r.text}`).join(" · ") : missing}</dd>
        <dt className="node-library__summary-key">Podklady</dt><dd className="node-library__summary-value">{workflow.materials.length ? workflow.materials.map((m) => m.caption || m.path).join(" · ") : missing}</dd>
        <dt className="node-library__summary-key">Akce</dt><dd className="node-library__summary-value">{workflow.actions.length ? workflow.actions.map((a, i) => `${i + 1}. ${a.label}`).join(" · ") : missing}</dd>
      </dl>
      <h4 className="node-library__category-title">Balíček pro model</h4>
      <p className="node-library__note">Jeden JSON s celou kartou. Stažení je jen čtení; nic se tím modelu neodesílá.</p>
      <div className="node-library__brief-actions">
        <button type="button" className="node-library__brief-button" data-testid="library-brief-fetch" disabled={loading} onClick={() => void download()}>
          {loading ? "Stahuji…" : "Stáhnout balíček pro model"}
        </button>
        {text && (
          <button
            type="button"
            className="node-library__brief-button"
            data-testid="library-brief-copy"
            onClick={() => { void navigator.clipboard?.writeText(text).then(() => setCopied(true)).catch(() => setCopied(false)); }}
          >
            {copied ? "Zkopírováno" : "Kopírovat JSON"}
          </button>
        )}
      </div>
      {briefError && <p className="node-library__empty" role="alert">{briefError}</p>}
      {text && <pre className="node-library__brief" data-testid="library-brief">{text}</pre>}
    </div>
  );
}
