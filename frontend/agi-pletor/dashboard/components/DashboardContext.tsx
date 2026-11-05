import { useEffect, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { contextView } from "../logic/context-view";

/** Podklady: sekce kontextu Pletora (znaků / strop, oříznuto) a pod nimi celý text z `GET /api/pletor/context`. Bez pollu, jen tlačítko Obnovit. */
export default function DashboardContext({ project, workspace }: { project: string; workspace: string }) {
  const [raw, setRaw] = useState<unknown>(null);
  const [error, setError] = useState("");
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true;
    api<unknown>(`/api/pletor/context?${new URLSearchParams({ project, workspace })}`).then(
      (next) => { if (live) { setRaw(next); setError(""); } },
      (failure: unknown) => { if (live) setError(failure instanceof Error ? failure.message : "Načtení selhalo."); },
    );
    return () => { live = false; };
  }, [project, workspace, tick]);
  const view = contextView(raw);
  return (
    <>
      <div><button type="button" className="pletor-dashboard__button" onClick={() => setTick(tick + 1)}>Obnovit</button></div>
      {error && <p className="pletor-dashboard__error" role="alert">{error}</p>}
      {view.problem && <p className="pletor-dashboard__error">{view.problem}</p>}
      <table className="pletor-dashboard__table">
        <thead><tr><th>Sekce</th><th>Znaků / strop</th><th /></tr></thead>
        <tbody>
          {view.sections.map((row, index) => (
            <tr key={index}><td>{row.title}</td><td>{row.size}</td><td>{row.truncated && <span className="pletor-dashboard__tag">oříznuto</span>}</td></tr>
          ))}
        </tbody>
      </table>
      <pre className="pletor-dashboard__pre">{view.text}</pre>
    </>
  );
}
