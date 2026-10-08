import { useEffect, useRef, useState } from "react";
import { fetchNodeBrief } from "@/shared/desktop-state/logic/api";
import { api } from "@/shared/types/logic/types";
import { asRecord, type AcceptedResult, type ResultHistory as History } from "../logic/handoff";
import SpecificationDiff from "./SpecificationDiff";

/** Saved evidence is shown separately from independently verified completion. */
export default function ResultHistory({ project, workspace, nodeId, revision }: { project: string; workspace: string; nodeId: string; revision: number }) {
  const [items, setItems] = useState<AcceptedResult[]>([]);
  const [version, setVersion] = useState("");
  const [specification, setSpecification] = useState<unknown>(null);
  const [before, setBefore] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const generation = useRef(0);
  useEffect(() => {
    let live = true;
    generation.current++;
    setLoading(true); setError(""); setItems([]); setSpecification(null); setBefore(null);
    fetchNodeBrief(project, workspace, nodeId).then((brief) => {
      if (!live) return;
      const history = asRecord(brief.resultHistory);
      setVersion(typeof brief.contextVersion === "string" ? brief.contextVersion : "");
      setSpecification(brief.specification);
      setItems(Array.isArray(history.items) ? history.items as AcceptedResult[] : []);
      setBefore(typeof history.nextBefore === "number" ? history.nextBefore : null);
    }).catch((e) => { if (live) setError(String(e)); }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; generation.current++; };
  }, [project, workspace, nodeId, revision, reload]);
  async function older() {
    if (!before || loading) return;
    const request = generation.current;
    setLoading(true); setError("");
    try {
      const history = await api<History & { nextBefore: number | null }>("/api/desktop-v3/agent-results?" + new URLSearchParams({ project, workspace, nodeId, before: String(before) }));
      if (request !== generation.current) return;
      setItems((current) => [...current, ...history.items.filter((item) => !current.some((existing) => existing.id === item.id))]);
      setBefore(history.nextBefore);
    } catch (e) { if (request === generation.current) setError(String(e)); }
    finally { if (request === generation.current) setLoading(false); }
  }
  return <div className="result-history">
    <p>Uložená hlášení agentů s původním zadáním. Uložení samo nepotvrzuje testy ani dokončení.</p>
    {loading && <p role="status">Načítám výsledky…</p>}
    {error && <p role="alert">{error}</p>}
    <button type="button" disabled={loading} onClick={() => setReload((value) => value + 1)}>Obnovit výsledky</button>
    {!loading && !error && !items.length && <p>Zatím není uložený výsledek.</p>}
    {items.map((item) => <details key={item.id} className="result-history__item"><summary>{item.agent || "Agent"} · {item.createdAt} · {item.binding !== "bound" ? "bez vazby na zadání" : item.contextVersion === version ? "aktuální zadání" : "⚠ Zadání se změnilo"}</summary>
      {item.binding === "bound" && item.contextVersion !== version && <SpecificationDiff before={item.specification} after={specification} />}
      <details><summary>Uložený výsledek a původní zadání</summary><pre>{JSON.stringify(item, null, 2)}</pre></details>
    </details>)}
    {before && <button type="button" disabled={loading} onClick={() => void older()}>Starší výsledky</button>}
  </div>;
}
