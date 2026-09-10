import { useEffect, useState } from "react";
import { api } from "./types";

type Run = { id: string; project_id: string; workspace: string; layer: string; status: string; message: string; output: string };
export default function PlanPanel({ project, dirty, enabled = true, initialWorkspace = "draft", initialLayer = "" }: { project: string; dirty: boolean; enabled?: boolean; initialWorkspace?: string; initialLayer?: string }) {
  const [workspace, setWorkspace] = useState(initialWorkspace);
  const [options, setOptions] = useState<{ id: string; label: string }[]>([]);
  const [layer, setLayer] = useState(initialLayer);
  const [preview, setPreview] = useState<{ digest: string; context: unknown } | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [active, setActive] = useState<Run | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [stop, setStop] = useState<Run | null>(null);
  useEffect(() => { if (!enabled) return; let alive = true; api<{ workspaces: typeof options }>("/api/project-workspaces?" + new URLSearchParams({ project })).then(x => { if (alive) { setOptions(x.workspaces); setWorkspace((old) => x.workspaces.some((option) => option.id === old) ? old : x.workspaces[0]?.id ?? "draft"); } }).catch(e => setError(String(e))); return () => { alive = false; }; }, [project, enabled]);
  useEffect(() => { if (!enabled) return; let alive = true; const refresh = () => api<{ runs: Run[]; active: Run | null }>("/api/llm/runs?" + new URLSearchParams({ project })).then(x => { if (alive) { setRuns(x.runs); setActive(x.active); } }).catch(e => { if (alive) setError(String(e)); }); refresh(); const timer = setInterval(refresh, 1000); return () => { alive = false; clearInterval(timer); }; }, [project, enabled]);
  useEffect(() => { setPreview(null); }, [workspace, layer]);
  async function action(fn: () => Promise<void>) { setBusy(true); setError(""); try { await fn(); } catch (e) { setError(String(e)); } finally { setBusy(false); } }
  return <section className="hub-card"><h2>Návrh přes Hermes · bez zápisu kódu</h2>
    <p>Jen uložené podklady. Návrh není coding agent ani důkaz dokončení. Přepnutí projektu existující běh nepřesměruje.</p>
    <label className="field">Rozsah návrhu<select aria-label="Rozsah návrhu" value={workspace} onChange={e => setWorkspace(e.target.value)}>{options.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}</select></label>
    <label className="field">ID vrstvy návrhu (prázdné = kořen)<input value={layer} onChange={e => setLayer(e.target.value)} /></label>
    <button disabled={busy || dirty} onClick={() => action(async () => setPreview(await api("/api/llm/preview?" + new URLSearchParams({ project, workspace, layer }))))}>Náhled kontextu návrhu</button>
    {preview && <><pre data-testid="llm-preview" style={{ maxHeight: 280, overflow: "auto", whiteSpace: "pre-wrap" }}>{JSON.stringify(preview, null, 2)}</pre><button disabled={busy || dirty || !!active} onClick={() => action(async () => { const r = await api<Run>("/api/llm/start", { project, workspace, layer, digest: preview.digest, confirmed: true }); setActive(r); setRuns(old => [r, ...old]); setPreview(null); })}>Potvrdit a spustit návrh</button></>}
    {error && <p role="alert">{error}</p>}
    {active && <div role="status"><code>{active.id}</code> · {active.status} · projekt {active.project_id}<button disabled={busy} onClick={() => setStop(active)}>Zastavit návrh</button></div>}
    {stop && <div role="dialog" aria-label="Zastavení návrhu"><p>Zastavit tento lokální procesní strom bez restartu? Účtování providera nelze tímto potvrdit.</p><button disabled={busy} onClick={() => setStop(null)}>Zrušit</button><button disabled={busy} onClick={() => action(async () => { const r = await api<Run>("/api/llm/stop", { project: stop.project_id, runId: stop.id, confirmed: true }); if (r.status === "stopping") throw new Error("Zastavení ještě není ověřeno."); setActive(null); setStop(null); })}>Potvrdit zastavení návrhu</button></div>}
    {runs.map(r => <details key={r.id}><summary>{r.status} · {r.id}</summary><p>{r.message}</p><pre style={{ whiteSpace: "pre-wrap", maxHeight: 350, overflow: "auto" }}>{r.output || "Výstup zatím není dostupný."}</pre></details>)}
  </section>;
}
