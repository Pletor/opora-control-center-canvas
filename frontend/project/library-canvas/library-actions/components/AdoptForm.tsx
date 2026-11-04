import { useEffect, useState } from "react";
import type { Project } from "@/shared/types/logic/types";
import { loadAdoptTargets, type AdoptTarget } from "../logic/adopt-targets";

/** „Převzít do projektu“: výběr projektu (výchozí otevřený) a domény nebo stránky, ke které kopie patří. Odeslání
 * hlásí rodiči, ten zapíše a otevře kopii. Chyba čtení domén zůstane větou, převzít jde i bez vazby na doménu. */
export default function AdoptForm({ projects, project, busy, onAdopt, onCancel }: {
  projects: Project[]; project: string; busy: boolean; onAdopt: (project: string, nodeId: string) => void; onCancel: () => void;
}) {
  const [target, setTarget] = useState(project || projects[0]?.id || "");
  const [nodeId, setNodeId] = useState("");
  const [choices, setChoices] = useState<AdoptTarget[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const chosen = projects.find((item) => item.id === target);
    let alive = true;
    setChoices(null); setNodeId(""); setError("");
    if (chosen) loadAdoptTargets(chosen).then((found) => { if (alive) { setChoices(found); setNodeId(found[0]?.id ?? ""); } },
      (cause) => { if (alive) { setChoices([]); setError(cause instanceof Error ? cause.message : String(cause)); } });
    return () => { alive = false; };
  }, [target, projects]);
  return <form className="library-actions__form" data-testid="library-adopt-form" onSubmit={(event) => { event.preventDefault(); if (target) onAdopt(target, nodeId); }}>
    <label className="library-actions__field">Projekt
      <select className="library-actions__input" value={target} onChange={(event) => setTarget(event.target.value)}>
        {projects.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select></label>
    <label className="library-actions__field">Doména nebo stránka
      <select className="library-actions__input" value={nodeId} disabled={!choices} data-testid="library-adopt-target" onChange={(event) => setNodeId(event.target.value)}>
        {!choices && <option value="">Načítám…</option>}
        {choices?.map((choice) => <option key={choice.id} value={choice.id}>{choice.label}</option>)}
        <option value="">bez vazby (jen podle slugu)</option>
      </select></label>
    {error && <p className="library-actions__error" role="alert">Domény se nepodařilo načíst: {error}</p>}
    <div className="library-actions__row">
      <button type="submit" className="library-actions__button library-actions__button--primary" disabled={busy || !target} data-testid="library-adopt-submit">Převzít</button>
      <button type="button" className="library-actions__button" onClick={onCancel}>Zrušit</button>
    </div>
  </form>;
}
