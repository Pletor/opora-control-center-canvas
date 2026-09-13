import { useEffect, useRef, useState } from "react";
import ConnectorsSection from "@/settings/components/ConnectorsSection";
import GeneralSection from "@/settings/components/GeneralSection";
import SkillsSection from "@/settings/components/SkillsSection";
import "@/settings/styles/settings.css";

type SectionId = "general" | "skills" | "connectors";

const NAV: { head: string; items: { id: SectionId; label: string }[] }[] = [
  { head: "Nastavení", items: [{ id: "general", label: "Obecné" }] },
  { head: "Přizpůsobení", items: [{ id: "skills", label: "Skills" }, { id: "connectors", label: "Connectors" }] },
];

/** Nastavení aplikace z levého dolního rohu: vlevo navigace, vpravo vybraná sekce. */
export default function SettingsDialog({ onClose, initial = "general" }: { onClose: () => void; initial?: SectionId }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [section, setSection] = useState<SectionId>(initial);
  useEffect(() => {
    const d = ref.current!;
    d.showModal();
    return () => d.close();
  }, []);
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
        {NAV.map((group) => (
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
        {section === "skills" && <SkillsSection />}
        {section === "connectors" && <ConnectorsSection />}
      </div>
    </dialog>
  );
}
