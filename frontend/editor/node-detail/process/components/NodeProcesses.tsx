import { useCallback, useEffect, useState } from "react";
import ProcessCard from "@/editor/node-detail/process/components/ProcessCard";
import { createProcess, listProcesses, readProcess, type Process, type ProcessWithAllowed, type Report } from "@/editor/node-detail/process/logic/processes";
import "@/editor/node-detail/process/styles/process.css";

/** Záložka Proces v detailu uzlu: procesy tohoto uzlu, založení nového, práce s vybraným. */
export default function NodeProcesses({ project, nodeId, readOnly }: { project: string; nodeId: string; readOnly: boolean }) {
  const [items, setItems] = useState<ProcessWithAllowed[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const [reports, setReports] = useState<Record<string, Report[]>>({});
  const [title, setTitle] = useState("");
  const [steps, setSteps] = useState("");
  const [worktree, setWorktree] = useState("");
  const [error, setError] = useState("");
  const [status, setStatus] = useState<"loading" | "ready">("loading");

  const reload = useCallback(async () => {
    try {
      const list = await listProcesses(project, nodeId);
      setItems(list);
      setStatus("ready");
    } catch (exc) {
      setError((exc as Error).message);
      setStatus("ready");
    }
  }, [project, nodeId]);

  useEffect(() => {
    setStatus("loading");
    reload();
  }, [reload]);

  async function openDetail(id: string) {
    setOpen(id);
    try {
      const detail = await readProcess(project, id);
      setReports((old) => ({ ...old, [id]: detail.reports }));
      setItems((old) => old.map((item) => (item.id === id ? { ...detail.process, allowed: detail.allowed } : item)));
    } catch (exc) {
      setError((exc as Error).message);
    }
  }

  async function submitNew() {
    if (!title.trim()) return setError("Zadejte název procesu.");
    try {
      await createProcess(project, nodeId, title.trim(), steps.split("\n").map((s) => s.trim()).filter(Boolean), worktree.trim() || null);
      setTitle("");
      setSteps("");
      setWorktree("");
      setError("");
      await reload();
    } catch (exc) {
      setError((exc as Error).message);
    }
  }

  function changed(process: Process) {
    setError("");
    reload().then(() => openDetail(process.id));
  }

  return (
    <div className="node-processes">
      {error && <p className="error-text" role="alert">{error}</p>}
      {status === "loading" && <p className="muted">Načítám procesy…</p>}
      {status === "ready" && items.length === 0 && <p className="muted">Uzel zatím nemá žádný proces.</p>}
      <ul className="process-list">
        {items.map((item) => (
          <li key={item.id}>
            <button type="button" className={"process-row" + (open === item.id ? " open" : "")} onClick={() => (open === item.id ? setOpen(null) : openDetail(item.id))}>
              <span className={"process-state state-" + item.state}>{{ draft: "Návrh", running: "Proces", done: "Hotovo", repair: "Oprava" }[item.state]}</span>
              <span className="process-title">{item.title}</span>
              <span className="muted">{item.steps.filter((s) => s.state === "done").length}/{item.steps.length} kroků</span>
            </button>
            {open === item.id && (
              <ProcessCard project={project} process={item} allowed={item.allowed} reports={reports[item.id] ?? []} onChange={changed} onError={setError} />
            )}
          </li>
        ))}
      </ul>
      {!readOnly && (
        <form
          className="process-new"
          onSubmit={(e) => {
            e.preventDefault();
            submitNew();
          }}
        >
          <h4>Nový proces</h4>
          <label className="field">Název<input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} /></label>
          <label className="field">Kroky (jeden na řádek)<textarea rows={3} value={steps} onChange={(e) => setSteps(e.target.value)} /></label>
          <label className="field">Worktree (wt-…), prázdné = bez worktree<input value={worktree} onChange={(e) => setWorktree(e.target.value)} placeholder="wt-nazev" /></label>
          <button type="submit" className="primary">Založit návrh</button>
        </form>
      )}
    </div>
  );
}
