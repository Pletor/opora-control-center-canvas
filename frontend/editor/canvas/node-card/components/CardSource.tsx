import { useState } from "react";
import { api, type SourceRef } from "@/shared/types/logic/types";

export default function CardSource({ source, project, workspace }: {
  source: SourceRef; project: string; workspace: string;
}) {
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  async function open() {
    if (busy || source.origin !== "existing") return;
    setBusy(true); setNotice("");
    try {
      await api("/api/workspace/open-file", { project, workspace, path: source.path,
        action: source.kind === "directory" ? "folder-vscode" : "vscode" });
      setNotice("Požadavek na otevření předán systému.");
    } catch (error) { setNotice(String(error)); }
    finally { setBusy(false); }
  }
  return <div className="node-card__source nodrag">
    <button type="button" className={`source-badge source-badge-${source.origin}`}
      disabled={busy || source.origin !== "existing"} title={source.origin === "existing" ? "Otevřít ve VS Code" : "Plánovaný zdroj"}
      onClick={(event) => { event.stopPropagation(); void open(); }}>
      @{source.path || (source.origin === "planned" ? "cesta neurčena" : "/")}
      {source.origin === "planned" ? " · plán" : ""}
    </button>
    {notice && <span role="status">{notice}</span>}
  </div>;
}
