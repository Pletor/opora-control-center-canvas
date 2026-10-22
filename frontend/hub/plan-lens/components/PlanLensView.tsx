import { lazy, Suspense } from "react";
import { usePlanLens } from "../logic/use-plan-lens";
import PlanLensStrip from "./PlanLensStrip";
import "@/hub/review-lens/styles/review-lens.css";
import "../styles/plan-lens.css";

// Plátno je stejné jako Lens karty (`hub/review-lens`): renderer a schéma se načtou líně, obrázek je `<img>` z Blob URL.
const LensStage = lazy(() => import("@/hub/review-lens/components/LensStage"));

/** Lens plánu celého projektu (`area` null) nebo jedné oblasti: čte endpoint sám, skládá pruh čísel a plátno. */
export default function PlanLensView({ project, workspace, area }: { project: string; workspace: string; area: string | null }) {
  const lens = usePlanLens(project, workspace, area);
  const data = lens.data;
  return <div className="plan-lens review-lens" data-oh-view="plan-lens" data-oh-plan-status={lens.status} data-oh-plan-scope={area ? "area" : "project"}>
    {lens.status === "error" && <p className="review-lens__warning" role="alert">{lens.error}</p>}
    {lens.status === "unavailable" && <section className="plan-lens__calm" data-oh-plan-unavailable="">
      <b className="plan-lens__calm-title">Lens plánu není na serveru k dispozici</b>
      <p className="plan-lens__calm-text">Tento server ještě neumí <code>GET /api/oporahub/plan-lens</code>. Po aktualizaci serveru se tu ukáže plán jako diagram: oblasti, karty, vazby z plánu a vazby v kódu.</p>
      <button type="button" className="plan-lens__reload" onClick={lens.reload}>Zkusit znovu</button>
    </section>}
    {(lens.status === "loading" || lens.status === "idle") && !data && <p className="review-lens__loading" data-oh-plan-loading="">Načítám Lens plánu…</p>}
    {data && <>
      <PlanLensStrip lens={data} busy={lens.status === "loading"} onReload={lens.reload} />
      <Suspense fallback={<p className="review-lens__loading">Načítám plátno…</p>}>
        <LensStage key={data.digest} record={{ spec: data.spec, headSha: null }} />
      </Suspense>
    </>}
  </div>;
}
