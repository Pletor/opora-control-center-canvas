import "../styles/pletor-dashboard.css";
import { useEffect, useRef, useState } from "react";
import PletorWorkshop from "@/agi-pletor/workshop/components/PletorWorkshop";
import { PARTS, parsePart, withPart, type PartId } from "../logic/dashboard-route";
import DashboardBrain from "./DashboardBrain";
import DashboardOverview from "./DashboardOverview";
import DashboardVoice from "./DashboardVoice";

type Props = { project: string; workspace: string; onBack: () => void };

/**
 * Velín AGI Pletor (`?screen=pletor`, docs/navrhy/2026-11-05-pletor-opora-dashboard.md §3): celá obrazovka s levou
 * navigací po částech. Aktivní část drží adresa (`part=`), takže odkaz otevře přímo Hlas nebo Dílnu. V1 umí Přehled,
 * Mozek a LLM, Hlas a Dílnu; ostatní části jen hlásí, ve kterém milníku přijdou. Esc vrací do kokpitu, kromě Dílny,
 * která si Esc bere sama (zavře se na Přehled).
 */
export default function PletorDashboard({ project, workspace, onBack }: Props) {
  const [part, setPart] = useState<PartId>(() => parsePart(location.search));
  const title = useRef<HTMLHeadingElement>(null);
  const back = useRef(onBack);
  back.current = onBack;
  const open = (next: PartId) => { setPart(next); history.replaceState(null, "", withPart(location.search, next)); };
  useEffect(() => { title.current?.focus(); }, []);
  useEffect(() => {
    if (part === "dilna") return;
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape" && !event.defaultPrevented && !event.isComposing) { event.preventDefault(); back.current(); } };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [part]);

  const info = PARTS.find((item) => item.id === part)!;
  return (
    <div className="pletor-dashboard">
      <header className="pletor-dashboard__head">
        <h1 ref={title} tabIndex={-1} className="pletor-dashboard__title">VELÍN · AGI Pletor</h1>
        <button type="button" className="pletor-dashboard__button" onClick={onBack}>Zpět do kokpitu</button>
      </header>
      <nav className="pletor-dashboard__nav" aria-label="Části velínu">
        <div role="tablist" aria-orientation="vertical" className="pletor-dashboard__tabs">
          {PARTS.map((item) => (
            <button key={item.id} type="button" role="tab" id={`pletor-dashboard-tab-${item.id}`} aria-selected={part === item.id}
              aria-controls="pletor-dashboard-panel" className="pletor-dashboard__tab" onClick={() => open(item.id)}>{item.label}</button>
          ))}
        </div>
      </nav>
      <main id="pletor-dashboard-panel" role="tabpanel" aria-labelledby={`pletor-dashboard-tab-${part}`} className="pletor-dashboard__content">
        {part === "prehled" && <DashboardOverview project={project} workspace={workspace} />}
        {part === "mozek" && <DashboardBrain project={project} workspace={workspace} />}
        {part === "hlas" && <DashboardVoice />}
        {part === "dilna" && <div className="pletor-dashboard__workshop"><PletorWorkshop onClose={() => open("prehled")} /></div>}
        {!info.ready && <p className="pletor-dashboard__note">Přijde v milníku {"milestone" in info ? info.milestone : ""}.</p>}
      </main>
    </div>
  );
}
