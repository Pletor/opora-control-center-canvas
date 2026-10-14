import { useState } from "react";
import { api } from "@/shared/types/logic/types";
import SpecificationDiff from "@/editor/llm-control/editor-context/components/SpecificationDiff";

export default function AssignmentWarning({ project, workspace, nodeId, resultId, source = "result" }: {
  project: string; workspace: string; nodeId: string; resultId: string; source?: "handoff" | "result";
}) {
  const [comparison, setComparison] = useState<{ before: unknown; after: unknown } | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function load() {
    setBusy(true); setError("");
    try {
      const value = await api<{ before: unknown; after: unknown }>("/api/desktop-v3/assignment-comparison?" +
        new URLSearchParams({ project, workspace, nodeId, id: resultId, source }));
      setComparison(value);
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }
  return <div className="nodrag nopan node-card__row node-card__row--warn">
    <button type="button" onClick={() => void load()} disabled={busy}>⚠ Zadání se změnilo · porovnat</button>
    {error && <p role="alert">{error}</p>}
    {comparison && <SpecificationDiff {...comparison} />}
  </div>;
}
