import { useEffect, useState } from "react";
import ProcessCard from "@/editor/node-detail/process/components/ProcessCard";
import { STATE_LABEL, listProcesses, readProcess, type Process, type ProcessState, type ProcessWithAllowed, type Report } from "@/editor/node-detail/process/logic/processes";
import "@/editor/node-detail/process/styles/process.css";

const ORDER: ProcessState[] = ["repair", "running", "draft", "done"];

/** Live Run: procesy celého projektu, nejdřív ty v opravě a běžící. Uzly se ukazují názvem. */
export default function ProcessOverview({ project, projectName, nodeNames, onOpenNode }: {
  project: string;
  projectName: string;
  nodeNames: Record<string, string>;
  onOpenNode: (id: string) => void;
}) {
  const [items, setItems] = useState<ProcessWithAllowed[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const [reports, setReports] = useState<Record<string, Report[]>>({});
  const [error, setError] = useState("");

  async function reload() {
    try {
      setItems(await listProcesses(project));
      setError("");
    } catch (exc) {
      setError((exc as Error).message);
    }
  }

  useEffect(() => {
    reload();
    const timer = window.setInterval(reload, 5000);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project]);

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

  function changed(process: Process) {
    reload().then(() => openDetail(process.id));
  }

  return (
    <div className="process-overview">
      <h2>Procesy · {projectName}</h2>
      {error && <p className="error-text" role="alert">{error}</p>}
      {items.length === 0 && !error && <p className="muted">V tomto projektu zatím žádný proces neběží.</p>}
      {ORDER.map((state) => {
        const group = items.filter((item) => item.state === state);
        if (group.length === 0) return null;
        return (
          <section key={state} className="process-overview-group">
            <h3>{STATE_LABEL[state]} · {group.length}</h3>
            <ul className="process-list">
              {group.map((item) => (
                <li key={item.id}>
                  <button type="button" className={"process-row" + (open === item.id ? " open" : "")} onClick={() => (open === item.id ? setOpen(null) : openDetail(item.id))}>
                    <span className={"process-state state-" + item.state}>{STATE_LABEL[item.state]}</span>
                    <span className="process-title">{item.title}</span>
                    {item.nodeId && (
                      <span
                        className="muted"
                        role="link"
                        tabIndex={0}
                        onClick={(e) => {
                          e.stopPropagation();
                          onOpenNode(item.nodeId!);
                        }}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") onOpenNode(item.nodeId!);
                        }}
                      >
                        uzel: {nodeNames[item.nodeId] ?? item.nodeId}
                      </span>
                    )}
                  </button>
                  {open === item.id && <ProcessCard project={project} process={item} allowed={item.allowed} reports={reports[item.id] ?? []} onChange={changed} onError={setError} />}
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
