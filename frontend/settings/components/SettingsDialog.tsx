import { useEffect, useRef, useState } from "react";
import AssistantSection from "@/settings/components/AssistantSection";
import CanvasSection from "@/settings/components/CanvasSection";
import ConnectorsSection from "@/settings/components/ConnectorsSection";
import GeneralSection from "@/settings/components/GeneralSection";
import ProjectSection, { type ProjectActions } from "@/settings/components/ProjectSection";
import SkillsSection from "@/settings/components/SkillsSection";
import type { SurfaceSettings } from "@/shared/surface-settings/logic/workspace-settings";
import "@/settings/styles/settings.css";

type SectionId = "general" | "canvas" | "assistant" | "project" | "skills" | "connectors";

/** Nastavení aplikace z levého dolního rohu: vlevo navigace, vpravo vybraná sekce. Jediné místo pro nastavení. */
export default function SettingsDialog({ onClose, initial = "general", surface, project }: {
  onClose: () => void;
  initial?: SectionId;
  surface: { value: SurfaceSettings; onChange: (value: SurfaceSettings) => void };
  /** Operace nad aktuálním projektem; na úvodní obrazovce chybí. */
  project?: ProjectActions;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const [section, setSection] = useState<SectionId>(initial);
  useEffect(() => {
    const d = ref.current!;
    d.showModal();
    return () => d.close();
  }, []);
  const nav: { head: string; items: { id: SectionId; label: string }[] }[] = [
    { head: "Nastavení", items: [{ id: "general", label: "Obecné" }, { id: "canvas", label: "Plátno" }, { id: "assistant", label: "Asistent" }] },
    ...(project ? [{ head: "Projekt", items: [{ id: "project" as SectionId, label: project.name }] }] : []),
    { head: "Přizpůsobení", items: [{ id: "skills", label: "Skills" }, { id: "connectors", label: "Connectors" }] },
  ];
  return (
    <dialog
      ref={ref}
      className="removal-dialog settings-dialog"
      aria-labelledby="app-settings-title"
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
    >
      <nav className="settings-nav" aria-label="Sekce nastavení">
        {nav.map((group) => (
          <div key={group.head}>
            <div className="menu-head">{group.head}</div>
            {group.items.map((item) => (
              <button type="button" key={item.id} className="menu-item" aria-current={section === item.id ? "page" : undefined} onClick={() => setSection(item.id)}>
                {item.label}
              </button>
            ))}
          </div>
        ))}
      </nav>
      <div className="settings-content">
        <header className="settings-head">
          <h2 id="app-settings-title">Nastavení</h2>
          <button type="button" aria-label="Zavřít nastavení" onClick={onClose}>×</button>
        </header>
        {section === "general" && <GeneralSection />}
        {section === "canvas" && <CanvasSection value={surface.value} onChange={surface.onChange} />}
        {section === "assistant" && <AssistantSection />}
        {section === "project" && project && <ProjectSection actions={project} onClose={onClose} />}
        {section === "skills" && <SkillsSection />}
        {section === "connectors" && <ConnectorsSection />}
      </div>
    </dialog>
  );
}
