import { useEffect, useRef, useState } from "react";
import { api, type Project, type Job, type ProjectSettings, type SettingsSnapshot } from "@/shared/types/logic/types";
import { ARCHITECTURE_OPTIONS, TENANCY_OPTIONS } from "@/shared/project-capabilities/logic/project-profile";
import AgentAutonomyBadge from "@/shared/agent-autonomy/components/AgentAutonomyBadge";
import AgentAutonomySwitch from "@/shared/agent-autonomy/components/AgentAutonomySwitch";
import SiteSettingsCard from "@/project-setup/site-settings/components/SiteSettingsCard";
import type { AgentAutonomyApi } from "@/shared/agent-autonomy/logic/use-agent-autonomy";
import HeartPipelineCard from "@/project-setup/heart-pipeline/components/HeartPipelineCard";
import { heartPipelineSummary } from "@/project-setup/heart-pipeline/logic/heart-pipeline";
import { useHeartData } from "@/project/heart-canvas/logic/use-heart-data";
import "@/project-setup/styles/project-home.css";

type Draft = SettingsSnapshot & { dirty: boolean };
const drafts = new Map<string, Draft>();

export default function ProjectHome({ projects, draftProject, projectId, jobs, autonomy, onChoose, onRefresh, onOpen, onOpenHeart, onRemove, onConnected }: {
  projects: Project[]; draftProject?: Project; projectId: string; jobs: Job[];
  /** Plná autonomie agentů otevřeného projektu (drží a ukládá App přes useAgentAutonomy). */
  autonomy: AgentAutonomyApi;
  onChoose: (id: string, kind?: string) => void; onRefresh: () => Promise<void>; onOpen: () => void; onRemove: () => void;
  /** Otevře samostatnou obrazovku srdce projektu (`screen=heart`, vyřizuje App). */
  onOpenHeart: () => void;
  onConnected?: () => void;
}) {
  const [form, setForm] = useState<Draft | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [kind, setKind] = useState("local");
  const [locator, setLocator] = useState("");
  const [sourceName, setSourceName] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [pendingJob, setPendingJob] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const generation = useRef(0);
  const current = useRef(projectId); current.current = projectId;
  const heart = useHeartData(projectId);
  useEffect(() => {
    const ticket = ++generation.current;
    setLoading(true); setError(""); setForm(null);
    api<SettingsSnapshot>("/api/project-settings?" + new URLSearchParams({ project: projectId }))
      .then((value) => {
        if (ticket !== generation.current) return;
        const cached = drafts.get(projectId);
        setForm(cached?.dirty ? cached : { ...value, dirty: false });
        if (cached?.dirty && cached.revision !== value.revision) setError("Nastavení se mezitím změnilo; rozepsané hodnoty jsou zachované.");
      }).catch((e) => { if (ticket === generation.current) setError(String(e)); })
      .finally(() => { if (ticket === generation.current) setLoading(false); });
    return () => { generation.current++; };
  }, [projectId, reload]);
  useEffect(() => {
    if (!pendingJob) return;
    const job = jobs.find((j) => j.id === pendingJob);
    if (job?.status === "complete") { setPendingJob(null); setLocator(""); setConfirmed(false); onChoose(job.project_id, "git"); onConnected?.(); }
    else if (job && ["failed", "interrupted"].includes(job.status)) { setPendingJob(null); setError(job.message); }
  }, [jobs, pendingJob]);
  function change(update: Partial<ProjectSettings>, name?: string) {
    if (!form) return;
    const next: Draft = { ...form, project: name === undefined ? form.project : { ...form.project, name }, settings: { ...form.settings, ...update }, dirty: true };
    drafts.set(projectId, next); setForm(next);
  }
  async function saveSettings() {
    if (!form || busy || loading) return;
    const selected = projectId, ticket = generation.current;
    setBusy(true); setError("");
    try {
      const value = await api<SettingsSnapshot>("/api/project-settings", { project: selected, expected_revision: form.revision, name: form.project.name, settings: form.settings });
      drafts.delete(selected);
      if (ticket === generation.current) setForm({ ...value, dirty: false });
      await onRefresh();
    } catch (e) { if (ticket === generation.current) setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  async function connect() {
    if (busy || pendingJob || !confirmed) return;
    setBusy(true); setError("");
    try {
      if (kind === "github") {
        const result = await api<{ jobId: string }>("/api/connect", { url: locator, approved: true });
        setPendingJob(result.jobId); await onRefresh();
      } else {
        const inferred = locator.split(/[\\/]/).filter(Boolean).pop() ?? "Nový projekt";
        const name = sourceName.trim() || inferred;
        const project = await api<Project>(kind === "local" ? "/api/local-project" : "/api/empty-project", kind === "local" ? { name, path: locator, confirmed: true } : { name, confirmed: true });
        await onRefresh(); onChoose(project.id, project.sourceKind); setLocator(""); setSourceName(""); setConfirmed(false); onConnected?.();
      }
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  return <div className="project-home">
    <aside className="hub-sidebar">
      <div className="hub-brand"><span className="symbol">O</span><div><strong>OPORA</strong><small>CONTROL CENTER</small></div></div>
      <div className="eyebrow">PROJEKTY A ZDROJE</div>
      <nav aria-label="Projekty">
        <button data-project-id="draft" aria-current={projectId === "draft" ? "page" : undefined} className={projectId === "draft" ? "hub-project active" : "hub-project"} disabled={busy} onClick={() => onChoose("draft", "builtin")}><strong>{draftProject?.name ?? "Lokální návrh"}</strong><small>Bez připojeného zdroje</small></button>
        {projects.map((p) => <button key={p.id} data-project-id={p.id} aria-current={projectId === p.id ? "page" : undefined} className={projectId === p.id ? "hub-project active" : "hub-project"} disabled={busy} onClick={() => onChoose(p.id, p.sourceKind)}><strong>{p.name}</strong><small>{p.sourceKind === "local" ? "Lokální složka" : p.sourceKind === "empty" ? "Lokální projekt" : "GitHub / Git"}</small></button>)}
      </nav>
      <form className="hub-connect" onSubmit={(e) => { e.preventDefault(); connect(); }}>
        <h3>Připojit zdroj</h3>
        <label className="field">Typ zdroje<select aria-label="Typ zdroje" value={kind} disabled={busy || !!pendingJob} onChange={(e) => { setKind(e.target.value); setConfirmed(false); }}><option value="local">Lokální složka</option><option value="github">GitHub repozitář</option><option value="empty">Nový prázdný projekt</option></select></label>
        {kind !== "github" && <label className="field">Název nového projektu<input aria-label="Název nového projektu" maxLength={120} required={kind === "empty"} value={sourceName} onChange={(e) => setSourceName(e.target.value)} disabled={busy || !!pendingJob} /></label>}
        {kind !== "empty" && <label className="field">Cesta nebo GitHub URL<input aria-label="Cesta nebo GitHub URL" required value={locator} disabled={busy || !!pendingJob} onChange={(e) => { setLocator(e.target.value); setConfirmed(false); }} placeholder={kind === "local" ? "P:/projekty/muj-projekt" : "https://github.com/owner/repo"} /></label>}
        <label className="check"><input type="checkbox" checked={confirmed} disabled={busy || !!pendingJob} onChange={(e) => setConfirmed(e.target.checked)} />Potvrzuji připojení vybraného zdroje.</label>
        <button className="primary wide" disabled={busy || !!pendingJob || !confirmed}>Připojit projekt</button>
        <p className="muted">{kind === "local" ? "Odkaz na složku a čtení názvů ve stromu. Obsahy souborů se automaticky nečtou, nekopírují ani nemění." : kind === "github" ? "Schválená spravovaná kopie Git. Hesla a tokeny do URL nepatří; přístup spravuje Git na serveru." : "Projekt a návrh zůstanou v datech OporaCC."}</p>
        {pendingJob && <p role="status">Připojuji repozitář na pozadí…</p>}
      </form>
    </aside>
    <main className="hub-main">
      <header className="hub-top"><div><div className="eyebrow">PROJEKT → ZADÁNÍ → PRACOVNÍ PLOCHA</div><h1>Opora Control Center</h1></div><button className="primary" disabled={loading || !form || busy} onClick={onOpen}>Otevřít Canvas</button></header>
      {error && <div className="hub-error" role="alert"><p>{error}</p>{form && <button disabled={busy} onClick={() => { drafts.delete(projectId); setReload(reload + 1); }}>Zahodit rozepsané a načíst uložené</button>}</div>}
      <section className="hub-heading"><h2>{form?.project.name ?? "Načítám projekt…"} <AgentAutonomyBadge autonomy={autonomy.autonomy} /></h2><p>{form?.project.sourcePath || form?.project.url || "Samostatný lokální návrh bez repozitáře"}</p>{projectId !== "draft" && <button className="danger" disabled={busy} onClick={onRemove}>Odebrat projekt z aplikace</button>}</section>
      <section className="hub-card">
        <h2>Nastavení projektu</h2>
        {form ? <form onSubmit={(e) => { e.preventDefault(); saveSettings(); }}>
          <div className="hub-fields"><label className="field">Název projektu<input value={form.project.name} maxLength={120} required disabled={busy} onChange={(e) => change({}, e.target.value)} /></label>
          <label className="field">Cílová platforma<select value={form.settings.platform} disabled={busy} onChange={(e) => change({ platform: e.target.value as ProjectSettings["platform"] })}><option value="web">Web</option><option value="app">Aplikace</option><option value="component">Komponenta</option></select></label></div>
          {/* Profil projektu: podle něj Knihovna a Agenti ukazují jen to, co k projektu sedí (docs/suplik-a-profil.md). */}
          <div className="hub-fields"><label className="field">Architektura<select aria-label="Architektura" value={form.settings.architecture} disabled={busy} onChange={(e) => change({ architecture: e.target.value as ProjectSettings["architecture"] })}><option value="">Nenastaveno – ukázat vše</option>{ARCHITECTURE_OPTIONS.map((option) => <option key={option.id} value={option.id}>{option.label} – {option.hint}</option>)}</select></label>
          <label className="field">Uživatelé<select aria-label="Uživatelé" value={form.settings.tenancy} disabled={busy} onChange={(e) => change({ tenancy: e.target.value as ProjectSettings["tenancy"] })}><option value="">Nenastaveno – ukázat vše</option>{TENANCY_OPTIONS.map((option) => <option key={option.id} value={option.id}>{option.label} – {option.hint}</option>)}</select></label></div>
          <label className="field">Cíl projektu<textarea aria-label="Cíl projektu" rows={4} maxLength={4000} value={form.settings.goal} disabled={busy} onChange={(e) => change({ goal: e.target.value })} /></label>
          <SiteSettingsCard site={form.settings.site} disabled={busy} onChange={(site) => change({ site })} />
          <div className="hub-actions"><span role="status" data-testid="project-settings-status">{busy ? "Ukládám…" : form.dirty ? "Neuložené nastavení" : form.revision ? `Uloženo · verze ${form.revision}` : "Výchozí nastavení"}</span><button className="primary" disabled={busy || !form.dirty}>Uložit nastavení projektu</button></div>
        </form> : <p role="status">Načítám nastavení…</p>}
        {/* Plná autonomie se ukládá hned a mimo revizi nastavení (docs/plna-autonomie-agenta.md). */}
        <AgentAutonomySwitch autonomy={autonomy.autonomy} disabled={autonomy.loading || busy} saving={autonomy.saving} error={autonomy.error} onChange={(full) => { void autonomy.setFull(full); }} />
      </section>
      <HeartPipelineCard summary={heartPipelineSummary(heart.workflow, heart.versions, heart.runs, heart.stalls)} loading={heart.loading} error={heart.error} onOpen={onOpenHeart} />
    </main>
  </div>;
}
