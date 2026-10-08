// Blok Pipeline u karty: řada profilů (jeden klik = přestavět), kdo proces určil a proč, pruh stavu a etapy.
// Proces běží sám (router + relace agentů); člověk jen přepíná a ubírá. Mutace posílá rodič (CanvasBlock).
import { useState } from "react";
import PipelineStageRow from "@/editor/workflow/card-pipeline/components/PipelineStageRow";
import {
  PROFILE_LABEL, STATUS_LABEL, SWITCHABLE, pipelineSummary, switchNeedsConfirm,
  type CardPipeline, type PipelineProfile,
} from "@/editor/workflow/card-pipeline/logic/pipeline-model";
import "@/editor/workflow/card-pipeline/styles/card-pipeline.css";

export default function PipelineBlock({
  pipeline, goal, disabled, onRoute, onMove, onRemove, onSkip, onEdit,
}: {
  pipeline: CardPipeline;
  goal: boolean;
  disabled: boolean;
  onRoute: (profile: PipelineProfile) => Promise<boolean>;
  onMove: (index: number, delta: number) => void;
  onRemove: (id: string) => void;
  onSkip: (id: string) => void;
  onEdit: (id: string, title: string, brief: string) => Promise<boolean>;
}) {
  const [confirming, setConfirming] = useState<PipelineProfile | null>(null);
  const summary = pipelineSummary(pipeline);
  const routed = pipeline.items.length > 0;
  function pick(profile: PipelineProfile) {
    if (routed && switchNeedsConfirm(pipeline) && confirming !== profile) return setConfirming(profile);
    setConfirming(null);
    onRoute(profile);
  }
  return (
    <div className="card-pipeline">
      <div className="pipeline-profiles" role="group" aria-label="Profil pipeline">
        {SWITCHABLE.map((profile) => (
          <button key={profile} type="button" disabled={disabled}
            className={"pipeline-chip" + (routed && pipeline.profile === profile ? " pipeline-chip--on" : "") + (confirming === profile ? " pipeline-chip--confirm" : "")}
            aria-pressed={routed && pipeline.profile === profile}
            title={confirming === profile ? "Etapy už běžely: klikni znovu a pipeline se přestaví" : `Přestavět pipeline na profil ${PROFILE_LABEL[profile]}`}
            onClick={() => pick(profile)}>
            {confirming === profile ? "Přestavět?" : PROFILE_LABEL[profile]}{profile === "goal" && goal ? " ●" : ""}
          </button>
        ))}
      </div>
      {routed ? (
        <p className="pipeline-routed">{pipeline.routedBy === "human" ? "Nastavil člověk" : `Router ${pipeline.routedBy ?? ""}`}{pipeline.reason ? `: ${pipeline.reason}` : ""}</p>
      ) : (
        <p className="pipeline-routed">Čeká na router; nebo vyber profil.</p>
      )}
      {summary.total > 0 && (
        <div className="pipeline-summary" aria-label={`Pipeline ${summary.finished} z ${summary.total}`}>
          <span className="pipeline-track" aria-hidden="true">
            {pipeline.items.filter((s) => s.approved).map((s) => <i key={s.id} className={`pipeline-dot pipeline-dot--${s.status}`} title={`${s.title}: ${STATUS_LABEL[s.status]}`} />)}
          </span>
          <span>{summary.finished}/{summary.total}</span>
          {summary.current && <span className="pipeline-next">na řadě: {summary.current.title}</span>}
          {summary.retries > 0 && <span className="pipeline-retries">↺ {summary.retries}× oprava</span>}
          {summary.stuck.length > 0 && <span className="pipeline-failed">čeká na tebe: {summary.stuck.map((s) => s.title).join(", ")}</span>}
        </div>
      )}
      <ol className="pipeline-stages">
        {pipeline.items.map((stage, index) => (
          <PipelineStageRow
            key={stage.id}
            stage={stage}
            first={index === 0}
            current={summary.current?.id === stage.id}
            disabled={disabled}
            onMove={(delta) => onMove(index, delta)}
            onRemove={() => onRemove(stage.id)}
            onSkip={() => onSkip(stage.id)}
            onEdit={(t, b) => onEdit(stage.id, t, b)}
          />
        ))}
      </ol>
    </div>
  );
}
