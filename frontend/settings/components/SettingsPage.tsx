import { useEffect, useRef, useState } from "react";
import CanvasSection from "./CanvasSection";
import ConnectorsSection from "./ConnectorsSection";
import GeneralSection from "./GeneralSection";
import JevKeySetting from "./JevKeySetting";
import ProjectSection, { type ProjectActions } from "./ProjectSection";
import SkillsSection from "./SkillsSection";
import SettingsOverview from "./SettingsOverview";
import ModelsSection from "./ModelsSection";
import type { SurfaceSettings } from "@/shared/surface-settings/logic/workspace-settings";
import "../styles/settings.css";
import "../styles/settings-page.css";

type SectionId = "overview" | "models" | "jev" | "skills" | "connectors" | "general" | "canvas" | "project";
const GROUPS: { title: string; items: [SectionId, string][] }[] = [
  { title: "PLETOR A SRDCE", items: [["overview", "Přehled organismu"], ["models", "Modely a účty"], ["jev", "Rozhodovací model Jev"]] },
  { title: "SCHOPNOSTI A PROPOJENÍ", items: [["skills", "Skills"], ["connectors", "Konektory a paměť"]] },
  { title: "PROSTŘEDÍ OPORY", items: [["general", "Rozhraní a automatika"], ["canvas", "Ovládání pláten"]] },
];

/** Full-page global administration, independent of the workflow canvas. */
export default function SettingsPage({ onClose, surface, project }: {
  onClose: () => void;
  surface: { value: SurfaceSettings; onChange: (value: SurfaceSettings) => void };
  project?: ProjectActions;
}) {
  const [section, setSection] = useState<SectionId>("overview");
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    heading.current?.focus();
    return () => { requestAnimationFrame(() => document.querySelector<HTMLButtonElement>(".account-button")?.focus()); };
  }, []);
  return <main className="settings-page" aria-labelledby="settings-page-title">
    <header className="settings-page__header">
      <div className="settings-page__brand"><span aria-hidden="true">O</span><div><strong>OPORA</strong><small>CONTROL CENTER</small></div></div>
      <span className="settings-page__scope">Globální nastavení · napříč projekty</span>
      <button type="button" onClick={onClose}>← Zpět do aplikace</button>
    </header>
    <div className="settings-page__body">
      <nav className="settings-page__nav" aria-label="Sekce globálního nastavení">
        {GROUPS.map((group) => <div key={group.title}><p className="settings-page__eyebrow">{group.title}</p>{group.items.map(([id, label]) => <button key={id} type="button" aria-current={section === id ? "page" : undefined} onClick={() => setSection(id)}>{label}</button>)}</div>)}
        {project && <div><p className="settings-page__eyebrow">KONTEXT NÁVRATU</p><button type="button" aria-current={section === "project" ? "page" : undefined} onClick={() => setSection("project")}>Operace projektu</button></div>}
      </nav>
      <div className="settings-page__content">
        <p className="settings-page__eyebrow">ZÁZEMÍ PRO ŘÍZENÍ OPORY</p>
        <h1 ref={heading} tabIndex={-1} id="settings-page-title">Nastavení Pletoru a srdce</h1>
        {section === "overview" && <SettingsOverview />}
        {section === "models" && <ModelsSection />}
        {section === "skills" && <SkillsSection />}
        {section === "connectors" && <ConnectorsSection />}
        {section === "jev" && <section className="settings-section"><h2>Rozhodovací model Jev</h2><p className="muted">Připojení rozhodovacího modelu používaného Brainem. Pracovní postup srdce se nastavuje samostatně na plátně 1.</p><JevKeySetting /></section>}
        {section === "general" && <GeneralSection />}
        {section === "canvas" && <CanvasSection value={surface.value} onChange={surface.onChange} />}
        {section === "project" && project && <ProjectSection actions={project} onClose={onClose} />}
      </div>
    </div>
  </main>;
}
