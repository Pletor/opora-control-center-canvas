import { useState, type FormEvent } from "react";
import { api } from "@/shared/types/logic/types";
import { useHubRead } from "@/hub/oporahub-mirror/logic/use-hub-read";
import { bindPayload, parseStatus, ROOT, statusUrl } from "../logic/folder-repository";
import "../styles/folder-repository.css";

/** Projekt z lokální složky: člověk jednou připojí GitHub repozitář jejího origin, aby Opora viděla PR a merge. */
export default function FolderRepository({ project }: { project: string }) {
  const read = useHubRead(project ? statusUrl(project) : null, parseStatus);
  const [repository, setRepository] = useState(""), [branch, setBranch] = useState("main");
  const [busy, setBusy] = useState(false), [error, setError] = useState(""), [note, setNote] = useState("");
  const status = read.data;
  if (!status?.applies) return null;
  const shownRepository = repository || status.detectedRepository || "";
  const payload = bindPayload(project, shownRepository, branch);
  async function run(work: () => Promise<string>) {
    setBusy(true); setError(""); setNote("");
    try { setNote(await work()); read.reload(); } catch (failure) { setError(failure instanceof Error ? failure.message : String(failure)); } finally { setBusy(false); }
  }
  const bind = (event: FormEvent) => {
    event.preventDefault();
    if (payload) void run(async () => {
      const result = await api<{ requeuedLinks?: number }>(ROOT, payload);
      return `Připojeno. Dříve připojená PR čekající na repozitář: ${result.requeuedLinks ?? 0}.`;
    });
  };
  const unbind = () => void run(async () => { await api(`${ROOT}/unbind`, { project }); return "Repozitář odpojen."; });
  return <section className="folder-repository" aria-label="GitHub repozitář složky projektu" aria-busy={busy || read.busy}>
    <h3 className="folder-repository__title">GitHub repozitář složky projektu</h3>
    <p className="folder-repository__lead">Projekt čte zdroj z lokální složky. Aby Opora viděla PR, review a merge, připojte jednou
      GitHub repozitář, na který ukazuje <code>origin</code> složky. Server ho ověří na disku.</p>
    {read.error && <p className="folder-repository__error" role="alert">{read.error}</p>}
    {error && <p className="folder-repository__error" role="alert">{error}</p>}
    {note && <p className="folder-repository__note" role="status">{note}</p>}
    {status.binding ? <div className="folder-repository__bound">
      <span>Připojeno: <strong>{status.binding.repository}</strong> · větev <strong>{status.binding.branch}</strong></span>
      <button type="button" className="folder-repository__button" disabled={busy || !status.canConfigure} onClick={unbind}>Odpojit</button>
    </div> : <form className="folder-repository__form" onSubmit={bind}>
      <label className="folder-repository__field">Repozitář (owner/název)
        <input value={shownRepository} onChange={event => setRepository(event.target.value)} placeholder="owner/repo" disabled={!status.canConfigure} />
      </label>
      <label className="folder-repository__field">Větev
        <input value={branch} onChange={event => setBranch(event.target.value)} disabled={!status.canConfigure} />
      </label>
      <button type="submit" className="folder-repository__button folder-repository__button--primary" disabled={busy || !payload || !status.canConfigure}>Připojit repozitář</button>
    </form>}
    {!status.canConfigure && status.unavailableReason && <p className="folder-repository__note">{status.unavailableReason}</p>}
  </section>;
}
