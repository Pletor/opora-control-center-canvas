// Pop-up „Přidat akci“: kategorie vlevo, předlohy vpravo; zdroj je knihovna v library/ přes API.
// Výběr bublá nahoru přes onSelect; kdo ho uloží, rozhoduje rodič.
import { useEffect, useState } from "react";
import type { PipelineLibrary, PipelineTemplate } from "@/shared/desktop-state/logic/types";
import { fetchPipelines, errorMessage } from "@/shared/desktop-state/logic/api";
import "@/editor/workflow/pipeline-picker/styles/pipeline-picker.css";

export default function PipelinePicker({ nodeName, onSelect, onClose }: { nodeName: string; onSelect: (p: PipelineTemplate) => void; onClose: () => void }) {
  const [library, setLibrary] = useState<PipelineLibrary | null>(null);
  const [error, setError] = useState("");
  const [category, setCategory] = useState("");
  useEffect(() => {
    let alive = true;
    fetchPipelines()
      .then((value) => {
        if (!alive) return;
        setLibrary(value);
        setCategory(value.categories[0]?.id ?? "");
      })
      .catch((e) => alive && setError(errorMessage(e)));
    return () => { alive = false; };
  }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  const current = library?.categories.find((c) => c.id === category) ?? library?.categories[0];
  return (
    <div className="pipeline-picker-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="pipeline-picker" role="dialog" aria-modal="true" aria-label="Vybrat pipeline">
        <header>
          <h2>Přidat akci · {nodeName}</h2>
          <button type="button" onClick={onClose}>Zavřít</button>
        </header>
        <div className="pipeline-picker-body">
          <ul className="pipeline-picker-categories" role="tablist">
            {library?.categories.map((c) => (
              <li key={c.id}>
                <button type="button" role="tab" aria-selected={c.id === current?.id} onClick={() => setCategory(c.id)}>
                  {c.label}
                </button>
              </li>
            ))}
          </ul>
          <div className="pipeline-picker-list">
            {error && <p role="alert" className="v3-error">{error}</p>}
            {!library && !error && <p role="status">Načítám knihovnu pipeline…</p>}
            {current && (
              <>
                <h3>{current.label}</h3>
                <p className="muted">{current.description}</p>
                {current.pipelines.map((p) => (
                  <button key={p.id} type="button" className="pipeline-card" onClick={() => onSelect(p)}>
                    <strong>{p.label}</strong>
                    <span>{p.description}</span>
                    <code>{p.id}</code>
                  </button>
                ))}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
