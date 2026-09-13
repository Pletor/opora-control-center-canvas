import { useEffect, useState } from "react";
import { api } from "@/types";
type Target = { id: string; path: string; branch: string; workspace: string; layer: string };
type Run = { id: string; project: string; status: string; message: string; targetPath: string; events: unknown[]; result: unknown; localTreeInactive: boolean; pid: number | null };
export default function CodingPanel({ project, dirty, enabled = true, initialWorkspace = "draft", initialLayer = "" }: { project: string; dirty: boolean; enabled?: boolean; initialWorkspace?: string; initialLayer?: string }) {
  const [targets, setTargets] = useState<Target[]>([]);
  const [targetId, setTargetId] = useState("");
  const [workspace, setWorkspace] = useState(initialWorkspace);
  const [options, setOptions] = useState<{ id: string; label: string }[]>([]);
  const [layer, setLayer] = useState(initialLayer);
  const [approved, setApproved] = useState(false);
  const [task, setTask] = useState("Implement add(a, b) in calculator.py as addition. Read the saved context, run tests before and after your edit. Complete the task with real tool calls.");
  const [preview, setPreview] = useState<{ digest: string } | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [active, setActive] = useState<Run | null>(null);
  const [stop, setStop] = useState<Run | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    const refresh = () => api<{ targets: Target[]; runs: Run[]; active: Run | null }>("/api/coding/runs?" + new URLSearchParams({ project })).then(x => { if (alive) { setTargets(x.targets); setRuns(x.runs); setActive(x.active); } }).catch(e => { if (alive) setError(String(e)); });
    refresh(); const timer = setInterval(refresh, 1000);
    api<{ workspaces: typeof options }>("/api/project-workspaces?" + new URLSearchParams({ project })).then(x => { if (alive) { setOptions(x.workspaces); setWorkspace((old) => x.workspaces.some((option) => option.id === old) ? old : x.workspaces[0]?.id ?? "draft"); } }).catch(e => { if (alive) setError(String(e)); });
    return () => { alive = false; clearInterval(timer); };
  }, [project, enabled]);
  useEffect(() => { setPreview(null); }, [targetId, task]);
  async function action(fn: () => Promise<void>) { setBusy(true); setError(""); try { await fn(); } catch (e) { setError(String(e)); } finally { setBusy(false); } }
  const target = targets.find(x => x.id === targetId);
  return <section className="hub-card"><h2>Skutečný coding agent · bezpečný testovací repo</h2>
    <p>Samostatný vykonávací režim. Hermes může číst a přepsat pouze calculator.py ve spravovaném testovacím repozitáři. Testy běží ve skutečném Dockeru bez sítě, pod neprivilegovaným uživatelem. Main, připojené složky, testy ani shell hostitele nejsou přístupné.</p>
    <p>První kontrakt je malý Python addition oracle: funkce add(a,b), jeden aritmetický return, bez importů a vedlejších účinků. Není to obecný agent nad libovolným projektem. Provider/model a časový limit přebírá z uloženého nastavení výše.</p>
    <label className="field">Zdroj uloženého kontextu<select value={workspace} onChange={e => { setWorkspace(e.target.value); setApproved(false); }}>{options.map(x => <option key={x.id} value={x.id}>{x.label}</option>)}</select></label>
    <label className="field">ID uzlu/sektoru pro coding kontext (prázdné = kořen)<input value={layer} onChange={e => { setLayer(e.target.value); setApproved(false); }} /></label>
    <label className="check"><input type="checkbox" checked={approved} onChange={e => setApproved(e.target.checked)} />Schvaluji oddělený testovací repozitář</label>
    <button disabled={busy || !approved || dirty} onClick={() => action(async () => { const value = await api<Target>("/api/coding/workspaces", { project, workspace, layer, confirmed: true }); setTargets(old => [value, ...old]); setTargetId(value.id); setApproved(false); })}>Vytvořit testovací repo</button>
    <label className="field">Schválený coding workspace<select value={targetId} onChange={e => setTargetId(e.target.value)}><option value="">Vyberte izolovaný workspace</option>{targets.map(x => <option value={x.id} key={x.id}>{x.id}</option>)}</select></label>
    {target && <p data-testid="coding-target"><code>{target.path}</code><br />{target.branch} · context {target.workspace}/{target.layer || "kořen"}</p>}
    <label className="field">Úkol pro coding agenta<textarea aria-label="Úkol pro coding agenta" rows={4} maxLength={4000} value={task} onChange={e => setTask(e.target.value)} /></label>
    <button disabled={busy || dirty || !targetId} onClick={() => action(async () => setPreview(await api("/api/coding/preview", { targetId, task }))) }>Náhled coding kontextu</button>
    {preview && <><pre data-testid="coding-preview" style={{ maxHeight: 240, overflow: "auto", whiteSpace: "pre-wrap" }}>{JSON.stringify(preview, null, 2)}</pre><p>Potvrzením se spustí placené provider volání přes Hermes a zápis do přesně uvedeného test repo. Jeden běh, bez automatického restartu. Časový limit není garance ceny.</p><button disabled={busy || dirty || !!active} onClick={() => action(async () => { const r = await api<Run>("/api/coding/start", { targetId, task, digest: preview.digest, confirmed: true }); setRuns(old => [r, ...old]); setActive(r); setPreview(null); })}>Potvrdit a spustit coding agenta</button></>}
    {error && <p role="alert">{error}</p>}
    {active && <div role="status">{active.id} · {active.status} · projekt {active.project}<button disabled={busy} onClick={() => setStop(active)}>Zastavit coding běh</button></div>}
    {stop && <div role="dialog" aria-label="Zastavení coding běhu"><p>Zastavit přesně tento lokální procesní strom a jeho testovací kontejner? Bez automatického restartu. Účtování providera zůstává neověřené.</p><button disabled={busy} onClick={() => setStop(null)}>Zrušit stop</button><button disabled={busy} onClick={() => action(async () => { const value = await api<Run>("/api/coding/stop", { runId: stop.id, project: stop.project, confirmed: true }); if (!value.localTreeInactive || value.status === "stopping") throw new Error("Zastavení ještě není ověřeno."); setActive(null); setStop(null); })}>Potvrdit stop coding běhu</button></div>}
    {runs.map(r => <article key={r.id} data-testid="coding-run"><h3>{r.status} · <code>{r.id}</code></h3><p>{r.message}</p><p>{r.targetPath} · PID {r.pid ?? "—"} · lokální strom {r.localTreeInactive ? "neaktivní" : "neověřen / běží"}</p><details open={r.status === "running"}><summary>Skutečné události a výstup</summary><pre style={{ maxHeight: 350, overflow: "auto", whiteSpace: "pre-wrap" }}>{JSON.stringify(r.events, null, 2)}</pre></details>{r.result != null && <details open><summary>Ověření, diff a testy</summary><pre style={{ maxHeight: 400, overflow: "auto", whiteSpace: "pre-wrap" }}>{JSON.stringify(r.result, null, 2)}</pre></details>}</article>)}
  </section>;
}
