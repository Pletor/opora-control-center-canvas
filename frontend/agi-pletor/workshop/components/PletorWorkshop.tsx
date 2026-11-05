import "../styles/pletor-workshop.css";
import { useEffect, useRef, useState } from "react";
import { useWorkshop } from "../logic/use-workshop";
import WorkshopGenerate from "./WorkshopGenerate";
import WorkshopList from "./WorkshopList";
import WorkshopSkillEditor from "./WorkshopSkillEditor";
import WorkshopToolEditor from "./WorkshopToolEditor";

/**
 * Dílna (docs/navrhy/2026-11-05-dilna-skillu.md §2a, §5): celoobrazovková vrstva nad nastavením Pletora. Vlevo seznamy
 * Skilly a Funkce, vedle dvě okna editoru (skill a funkce). Rodič drží `useWorkshop`; dílky dostávají data a hlásí změny.
 * Esc a „Zavřít“ volají `onClose` (panel nastavení pak vrátí focus na záložku Dílna).
 */
export default function PletorWorkshop({ onClose }: { onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const w = useWorkshop();
  const { state } = w;
  const [armed, setArmed] = useState(false);
  const dirty = w.skillDirty || w.toolDirty;
  // Neuložená změna se zavřením neztratí potichu: první Esc/Zavřít jen varuje, druhé zavře.
  const requestClose = () => { if (dirty && !armed) setArmed(true); else onClose(); };
  const close = useRef(requestClose);
  close.current = requestClose;

  useEffect(() => {
    ref.current?.focus();
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") { event.preventDefault(); close.current(); } };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const skillName = state.skill?.name ?? null;
  return (
    <div ref={ref} className="pletor-workshop" role="dialog" aria-modal="true" aria-label="Dílna" tabIndex={-1}>
      <header className="pletor-workshop__head">
        <strong className="pletor-workshop__title">Dílna</strong>
        <span className={"pletor-workshop__note" + (armed && dirty ? " pletor-workshop__note--warn" : "")} role="status">
          {armed && dirty ? "Neuložené změny. Zavřít znovu = zahodit." : w.busy ? w.note ?? "Pracuji…" : w.note ?? "Skilly a měřitelné funkce Pletora."}
        </span>
        <button type="button" className="pletor-workshop__button" onClick={() => void w.refresh()} disabled={w.busy}>Obnovit</button>
        <button type="button" className="pletor-workshop__button" onClick={requestClose}>Zavřít</button>
      </header>
      <div className="pletor-workshop__body">
        <nav className="pletor-workshop__side" aria-label="Skilly a funkce">
          <WorkshopList title="Skilly" newLabel="Nový skill" busy={w.busy} selected={skillName} onSelect={w.selectSkill} onCreate={(name) => void w.createSkill(name)}
            items={w.skills.map((s) => ({ name: s.name, hint: s.description }))} />
          <WorkshopList title="Funkce" newLabel="Nová funkce" busy={w.busy} selected={state.tool?.name ?? null} onSelect={w.selectTool}
            onCreate={(name) => void w.createTool(name)} items={w.tools.map((t) => ({ name: t.name, hint: `${t.cases} případů měření` }))} />
          <WorkshopGenerate busy={w.busy} blocked={w.toolDirty} onGenerate={(name, intent) => void w.generateTool(name, intent)} />
        </nav>
        <WorkshopSkillEditor doc={state.skill} files={w.skills.find((s) => s.name === skillName)?.files ?? []} dirty={w.skillDirty}
          pending={state.pending?.kind === "skill"} busy={w.busy} onFile={(path) => { w.selectFile(path); }} onEdit={w.editSkill}
          onSave={() => void w.saveSkill()} onDiscard={w.discard} onKeep={w.keep} />
        <WorkshopToolEditor doc={state.tool} measure={state.measure} dirty={w.toolDirty} pending={state.pending?.kind === "tool"} busy={w.busy}
          onEdit={w.editTool} onSave={() => void w.saveTool()} onMeasure={() => void w.measure()} onDiscard={w.discard} onKeep={w.keep} />
      </div>
    </div>
  );
}
