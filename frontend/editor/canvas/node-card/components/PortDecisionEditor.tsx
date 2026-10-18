import { useState } from "react";
import type { BlockPortDef } from "@/shared/desktop-state/logic/types";
import { useScopedSaveParticipant } from "@/shared/hooks/components/save-scope-context";

export default function PortDecisionEditor({ port, blockId, disabled, onSave }: {
  port: BlockPortDef; blockId: string; disabled: boolean;
  onSave: (status: "chosen" | "rejected" | "", reason: string) => void;
}) {
  const [status, setStatus] = useState<"chosen" | "rejected" | "">(port.status ?? "");
  const [reason, setReason] = useState(port.reason ?? "");
  // Klíč editoru je id portu, takže uložené rozhodnutí ze serveru převezme jen nerozepsaný editor.
  const [base, setBase] = useState({ status: port.status ?? "", reason: port.reason ?? "" });
  if (base.status !== (port.status ?? "") || base.reason !== (port.reason ?? "")) {
    setBase({ status: port.status ?? "", reason: port.reason ?? "" });
    if (status === base.status && reason === base.reason) { setStatus(port.status ?? ""); setReason(port.reason ?? ""); }
  }
  const dirty = status !== (port.status ?? "") || reason !== (port.reason ?? "");
  useScopedSaveParticipant({ id: `port-decision:${blockId}:${port.id}`, label: `Rozhodnutí portu ${port.label}`,
    dirty, isDirty: () => dirty, blocked: "Uložte nebo zrušte rozepsané rozhodnutí portu." });
  return <details className="nodrag nopan node-card__port-editor" data-dirty={dirty || undefined} onClick={e => e.stopPropagation()} onDoubleClick={e => e.stopPropagation()}>
    <summary title="Rozhodnutí portu: zvolit nebo zamítnout s důvodem" aria-label="Rozhodnutí portu">⚖</summary>
    <select aria-label={`Rozhodnutí portu ${port.label}`} disabled={disabled} value={status}
      onChange={e => setStatus(e.target.value as typeof status)}>
      <option value="">Nerozhodnuto</option><option value="chosen">Vybráno</option><option value="rejected">Zamítnuto</option>
    </select>
    <textarea aria-label={`Důvod rozhodnutí ${port.label}`} disabled={disabled || !status} value={reason}
      maxLength={4000} onChange={e => setReason(e.target.value)} />
    {dirty && <><button type="button" disabled={disabled || (!!status && !reason.trim())}
      onClick={() => onSave(status, reason)}>Uložit rozhodnutí</button>
      <button type="button" onClick={() => { setStatus(port.status ?? ""); setReason(port.reason ?? ""); }}>Zrušit</button></>}
  </details>;
}
