import { lazy, Suspense } from "react";
import { shownLens } from "../logic/lens-read";
import type { LensState } from "../logic/use-review-lens";
import LensHeader from "./LensHeader";
import "../styles/review-lens.css";

// Renderer PR Lens a schéma (zod) jsou těžké a potřebuje je jen tahle záložka: načtou se líně.
const LensStage = lazy(() => import("./LensStage"));

/** Prostor Lens: hlavička s fakty o specu, plátno s průvodcem a panely; bez specu poctivé vysvětlení. */
export default function ReviewLensPanel({ nodeId, state }: { nodeId: string; state: LensState }) {
  const shown = shownLens(state.read);
  return <div className="review-lens" data-oh-view="card-lens" data-oh-node-id={nodeId} data-oh-lens-kind={shown?.kind ?? "none"}
    data-oh-head-sha={shown?.headSha ?? ""}>
    {state.error && <p className="review-lens__warning" role="alert">{state.error}</p>}
    {shown?.spec ? <>
      <LensHeader record={shown} hasArea={!!state.read?.area} />
      <Suspense fallback={<p className="review-lens__loading" data-oh-lens-loading="">Načítám plátno…</p>}>
        <LensStage key={`${shown.kind}:${shown.headSha ?? shown.createdAt}`} record={shown} />
      </Suspense>
    </> : <LensEmpty busy={state.busy} />}
  </div>;
}

function LensEmpty({ busy }: { busy: boolean }) {
  if (busy) return <p className="review-lens__loading">Načítám Lens karty…</p>;
  return <section className="review-lens__empty" data-oh-lens-empty="">
    <b className="review-lens__empty-title">Lens zatím není</b>
    <p>Lens je prostor mezi plánem a kódem: ukáže, co změna dělá, po částech, vazbách a tocích dat, s cestami a řádky v kódu.</p>
    <ol className="review-lens__empty-list">
      <li><b>Před kódem</b> pracovník během běhu nakreslí mapu oblasti podle přijatého plánu (<code>kind: area</code>); záložka pak nese odznak „plán“.</li>
      <li><b>Po otevření PR</b> nakreslí graf změny pro aktuální hlavu (<code>pr-lens validate</code>) a pošle spec s lease tokenem běhu na <code>POST /api/oporahub/review-jobs/lens</code>.</li>
      <li><b>Agenti</b> čtou stejný spec jako data, ne obrázky: <code>GET /api/oporahub/review-lens?project&amp;workspace&amp;nodeId</code>.</li>
    </ol>
  </section>;
}
