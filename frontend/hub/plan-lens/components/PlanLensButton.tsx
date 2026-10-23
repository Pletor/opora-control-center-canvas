import { useState } from "react";
import { planLensTitle } from "../logic/plan-lens-stats";
import PlanLensDialog from "./PlanLensDialog";
import "../styles/plan-lens.css";

type Props = { project: string; workspace: string; area?: string | null; areaName?: string; className?: string };

/** Spouštěč: tlačítko „Lens plánu“ (projekt) nebo „Lens oblasti“ (s `area`), které drží jen to, zda je okno otevřené. */
export default function PlanLensButton({ project, workspace, area = null, areaName = "", className = "" }: Props) {
  const [open, setOpen] = useState(false);
  const label = area ? "Lens oblasti" : "Lens plánu";
  return <>
    <button type="button" className={`plan-lens__open${className ? ` ${className}` : ""}`} disabled={!project || !workspace}
      data-oh-plan-lens-open={area ? "area" : "project"} title={area ? "Karty oblasti, vazby z plánu a vazby v kódu jako diagram" : "Oblasti a předávky celého plánu jako diagram"}
      onClick={() => setOpen(true)}>◫ {label}</button>
    {open && <PlanLensDialog project={project} workspace={workspace} area={area} title={planLensTitle(area, areaName)} onClose={() => setOpen(false)} />}
  </>;
}
