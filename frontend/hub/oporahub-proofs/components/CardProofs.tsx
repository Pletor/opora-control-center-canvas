import { useState } from "react";
import type { AgentState } from "@/hub/oporahub-agent-state/logic/agent-state";
import { ToneChip } from "@/hub/oporahub-health/components/HealthMark";
import JsonMirror from "@/hub/oporahub-mirror/components/JsonMirror";
import { useHubRead } from "@/hub/oporahub-mirror/logic/use-hub-read";
import { api, ApiError } from "@/shared/types/logic/types";
import { parseProofs, proofActions, proofRows, proofsEndpoint, type ProofAction } from "../logic/card-proofs";
import "../styles/oporahub-proofs.css";

type Props = { project: string; workspace: string; nodeId: string; state: AgentState | null; onOpenLedger: () => void };

/** Rozhodnutí `verification.fix`: člověk založí (idempotentně) návrh karty „Opravit formální ověření“. */
function FixButton({ action, project, workspace }: { action: ProofAction; project: string; workspace: string }) {
  const [result, setResult] = useState<{ busy: boolean; text: string; tone: "ok" | "bad" | "gap" }>({ busy: false, text: "", tone: "gap" });
  async function run() {
    setResult({ busy: true, text: "Zakládám návrh…", tone: "gap" });
    try {
      await api(action.path, { project, workspace });
      setResult({ busy: false, text: "✓ Návrh opravy je založený; přijímá ho člověk v Přijímání návrhů.", tone: "ok" });
    } catch (error) {
      const text = error instanceof ApiError && error.status === 409 ? "Pro tento výsledek se návrh opravy nezakládá (jen protipříklad nebo selhání)."
        : error instanceof Error ? error.message : "Návrh opravy se nepodařilo založit.";
      setResult({ busy: false, text: `✕ ${text}`, tone: "bad" });
    }
  }
  return <span className="oporahub-proofs__fix">
    <button type="button" className="oporahub-proofs__button" onClick={run} disabled={result.busy}
      data-oh-action-id={action.id} data-oh-verb={action.verb} data-oh-action-status={action.status}>Založit návrh opravy</button>
    {result.text && <span role="status"><ToneChip tone={result.tone}>{result.text}</ToneChip></span>}
  </span>;
}

/** Formální důkazy karty: Lean, TLC a shoda s implementací, vždy s úrovní důvěry. */
export default function CardProofs({ project, workspace, nodeId, state, onOpenLedger }: Props) {
  const read = useHubRead(project && workspace && nodeId ? proofsEndpoint(project, workspace, nodeId) : null, parseProofs);
  const records = (read.data ?? []).filter(item => !item.nodeId || item.nodeId === nodeId);
  const rows = proofRows(records, state?.heads.acceptedHead ?? null);
  const actions = proofActions(state?.actions ?? [], records);
  return <section className="oporahub-proofs" aria-label="Formální důkazy karty">
    <header className="oporahub-proofs__head"><h2 className="oporahub-proofs__title">Formální důkazy</h2>
      <span className="oporahub-proofs__note">model není důkaz implementace</span>
      <button type="button" className="oporahub-proofs__button" onClick={onOpenLedger}>Kniha důkazů</button></header>
    <JsonMirror id="oh-card-proofs" value={{ nodeId, rows, actions }} />
    <div className="oporahub-proofs__body">
      {read.busy && !read.data && <p className="oporahub-proofs__note" role="status">Načítám formální podklady…</p>}
      {read.error && <p className="oporahub-proofs__note" role="alert">{read.error}</p>}
      {rows.map(row => <div key={row.kind} className={`oporahub-proofs__row oporahub-proofs__row--${row.tone}`}
        data-oh-proof-kind={row.kind} data-oh-proof-status={row.status} data-oh-trust={row.trust ?? ""} data-oh-verification={row.verificationId}>
        <b className="oporahub-proofs__kind">{row.label}</b>
        <ToneChip tone={row.tone}>{row.glyph} {row.word}</ToneChip>
        {row.trust && <ToneChip tone={row.trust === "ci-verified" ? "ok" : "warn"}>{row.trust === "ci-verified" ? "✓" : "◷"} {row.trustLabel}</ToneChip>}
        {row.checkName && <code className="oporahub-proofs__mono">{row.checkName}</code>}
        {row.commit && <code className="oporahub-proofs__mono">{row.commit}</code>}
        <span className="oporahub-proofs__note">{row.historical ? "⚠ " : ""}{row.note}</span>
      </div>)}
      {actions.map(action => <div key={action.id} className="oporahub-proofs__action">
        {action.verb === "verification.fix"
          ? <><span className="oporahub-proofs__note">Rozhodnutí: protipříklad nebo selhání → návrh opravy (přijímá člověk).</span>
            <FixButton action={action} project={project} workspace={workspace} /></>
          : <span className="oporahub-proofs__note" data-oh-action-id={action.id} data-oh-verb={action.verb} data-oh-action-status={action.status}>
            ◷ Agent má prošetřit výsledek {action.targetId.slice(0, 12)} (verification.investigate).</span>}
      </div>)}
    </div>
  </section>;
}
