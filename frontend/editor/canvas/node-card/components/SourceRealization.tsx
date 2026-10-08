import { useState } from "react";
import { useScopedSaveParticipant } from "@/shared/hooks/logic/save-scope-context";
import { safeDesignUrl } from "./CardDesign";
import type { CanvasNode } from "@/shared/types/logic/types";
import type { SourceStatus } from "../logic/use-source-status";

export default function SourceRealization({ nodeId, value, status, disabled, mergePassed, save }: {
  nodeId: string; value?: CanvasNode["realization"]; status?: SourceStatus; disabled: boolean; mergePassed: boolean;
  save: (commit: string, prUrl: string) => Promise<void>;
}) {
  const [commit, setCommit] = useState(value?.commit ?? "");
  const [prUrl, setPrUrl] = useState(value?.prUrl ?? "");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const dirty = commit !== (value?.commit ?? "") || prUrl !== (value?.prUrl ?? "");
  useScopedSaveParticipant({ id: `source-realization:${nodeId}`, label: "Ověření výstupu", dirty,
    blocked: "Dokončete ověření výstupu nebo zrušte rozepsanou stopu commitu/PR." });
  return <details className="nodrag nopan" style={{ padding: "6px 12px" }}>
    <summary>{status?.status === "missing" ? "⚠ Cesta chybí · " : status?.status === "present" ? "✓ Cesta existuje · " : "Cesta neověřena · "}
      {value ? `Commit/PR ${value.commit ? value.commit.slice(0, 10) : ""}` : "Ověřit výstup po merge"}</summary>
    {value && <p>{value.commit && <code>{value.commit}</code>} {value.prUrl && safeDesignUrl(value.prUrl) && <a href={value.prUrl} target="_blank" rel="noopener noreferrer">PR</a>} · Ověření disku {value.verifiedAt}</p>}
    <p>Disk se ověří nyní. Commit/PR je uvedená stopa; vzdálené sloučení se automaticky nekontroluje.</p>
    <fieldset disabled={disabled || busy}><label>Commit SHA<input value={commit} maxLength={64} onChange={e => setCommit(e.target.value)} /></label>
      <label>Odkaz na PR<input type="url" value={prUrl} maxLength={2048} onChange={e => setPrUrl(e.target.value)} /></label>
      {!mergePassed && <p>Nejprve doložte merge se stavem passed v důkazech karty.</p>}
      <button type="button" disabled={!mergePassed || (!commit && !prUrl)} onClick={async () => {
        setBusy(true); setMessage("");
        try { await save(commit, prUrl); setMessage("Zdroj ověřen a uložen jako existující."); }
        catch (error) { setMessage(String(error)); }
        finally { setBusy(false); }
      }}>Ověřit a převést na existující</button>
      {dirty && <button type="button" onClick={() => { setCommit(value?.commit ?? ""); setPrUrl(value?.prUrl ?? ""); }}>Zrušit</button>}
    </fieldset>{message && <p role="status">{message}</p>}
  </details>;
}
