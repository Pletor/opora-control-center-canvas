import { useState } from "react";
import { putPletorLlm } from "@/agi-pletor/hud/logic/pletor-client";
import { modelProblem, REASONING, savedNote, type ModelRow } from "../logic/settings-view";

type Props = { target: "claude" | "codex"; title: string; row: ModelRow; onSaved: () => void };

/** Jeden řádek „Modely LLM“: aktuální model, pole s novým, u Codexu úroveň uvažování a Uložit. Nedostupná sekce ukáže jen důvod. */
export default function SettingsModelForm({ target, title, row, onSaved }: Props) {
  const [model, setModel] = useState(row.model);
  const [reasoning, setReasoning] = useState<string>(row.reasoning ?? "");
  const [note, setNote] = useState<{ text: string; error: boolean } | null>(null);
  if (!row.available) return <section className="pletor-dashboard__setting" aria-label={title}><h3 className="pletor-dashboard__group-title">{title}</h3><p className="pletor-dashboard__note">{row.reason || "nedostupné"}</p></section>;
  const problem = modelProblem(model);
  const save = () => {
    putPletorLlm(target, { model, ...(target === "codex" && reasoning ? { reasoning } : {}) }).then(
      (backup) => { setNote({ text: savedNote(backup), error: false }); onSaved(); },
      (error: unknown) => setNote({ text: error instanceof Error ? error.message : "Uložení selhalo.", error: true }),
    );
  };
  return (
    <section className="pletor-dashboard__setting" aria-label={title}>
      <h3 className="pletor-dashboard__group-title">{title}</h3>
      <p className="pletor-dashboard__note">Teď: <b>{row.model || "výchozí"}</b></p>
      <div className="pletor-dashboard__tools">
        <input className="pletor-dashboard__input" aria-label={`Model ${title}`} value={model} onChange={(event) => { setModel(event.target.value); setNote(null); }} />
        {target === "codex" && (
          <select className="pletor-dashboard__input" aria-label="Úroveň uvažování" value={reasoning} onChange={(event) => setReasoning(event.target.value)}>
            <option value="">beze změny</option>
            {REASONING.map((level) => <option key={level} value={level}>{level}</option>)}
          </select>
        )}
        <button type="button" className="pletor-dashboard__button" disabled={problem !== null} title={problem ?? undefined} onClick={save}>Uložit</button>
      </div>
      {note && <p className={note.error ? "pletor-dashboard__error" : "pletor-dashboard__note"} role={note.error ? "alert" : "status"}>{note.text}</p>}
    </section>
  );
}
