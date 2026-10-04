import { useEffect, useState } from "react";
import { fetchNodeBrief } from "@/shared/desktop-state/logic/api";
import { api } from "@/shared/types/logic/types";
import { asRecord, type AcceptedResult, type ResultHistory as History } from "../logic/handoff";

/** Saved evidence is shown separately from independently verified completion. */
export default function ResultHistory({ project, workspace, nodeId, revision }: { project: string; workspace: string; nodeId: string; revision: number }) {
  const [items, setItems] = useState<AcceptedResult[]>([]);
  const [version, setVersion] = useState("");
  const [before, setBefore] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let live = true;
    setLoading(true); setError("");
    fetchNodeBrief(project, workspace, nodeId).then((brief) => {
      if (!live) return;
      const history = asRecord(brief.resultHistory);
      setVersion(typeof brief.contextVersion === "string" ? brief.contextVersion : "");
      setItems(Array.isArray(history.items) ? history.items as AcceptedResult[] : []);
      setBefore(typeof history.nextBefore === "number" ? history.nextBefore : null);
    }).catch((e) => { if (live) setError(String(e)); }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [project, workspace, nodeId, revision, reload]);
  async function older() {
    if (!before || loading) return;
    setLoading(true); setError("");
    try {
      const history = await api<History & { nextBefore: number | null }>("/api/desktop-v3/agent-results?" + new URLSearchParams({ project, workspace, nodeId, before: String(before) }));
      setItems((current) => [...current, ...history.items.filter((item) => !current.some((existing) => existing.id === item.id))]);
      setBefore(history.nextBefore);
    } catch (e) { setError(String(e)); }
    finally { setLoading(false); }
  }
  return <div className="result-history">
    <p>Uložená hlášení agentů s původním zadáním. Uložení samo nepotvrzuje testy ani dokončení.</p>
    {loading && <p role="status">Načítám výsledky…</p>}
    {error && <p role="alert">{error}</p>}
    <button type="button" disabled={loading} onClick={() => setReload((value) => value + 1)}>Obnovit výsledky</button>
    {!loading && !error && !items.length && <p>Zatím není uložený výsledek.</p>}
    {items.map((item) => <details key={item.id} className="result-history__item"><summary>{item.agent || "Agent"} · {item.createdAt} · {item.binding !== "bound" ? "bez vazby na zadání" : item.contextVersion === version ? "aktuální zadání" : "jiná verze zadání"}</summary><pre>{JSON.stringify(item, null, 2)}</pre></details>)}
    {before && <button type="button" disabled={loading} onClick={() => void older()}>Starší výsledky</button>}
  </div>;
}
