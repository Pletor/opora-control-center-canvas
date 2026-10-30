import { useRef } from "react";
import { createPortal } from "react-dom";
import JsonMirror from "@/hub/oporahub-mirror/components/JsonMirror";
import { useNow } from "@/editor/node-detail/agent-summary/logic/use-now";
import type { CanvasNode } from "@/shared/types/logic/types";
import type { CardTab } from "../logic/card-drawer-store";
import type { DrawerEditor } from "../logic/drawer-editor";
import { dodView } from "../logic/card-dod";
import { nextAction, statusLine } from "../logic/card-header";
import { useCardData, type CardData } from "../logic/use-card-data";
import { useDrawerFocus } from "../logic/use-drawer-focus";
import { readSteps } from "../spec-tab/logic/spec-diff";
import { leaseView } from "../run-tab/logic/run-view";
import { stepProgress, stepRows } from "../steps-tab/logic/step-status";
import DrawerHeader from "./DrawerHeader";
import DrawerTabs from "./DrawerTabs";
import DrawerFooter from "./DrawerFooter";
import SpecTab from "../spec-tab/components/SpecTab";
import StepsTab from "../steps-tab/components/StepsTab";
import RunTab from "../run-tab/components/RunTab";
import ReviewTab from "../review-tab/components/ReviewTab";
import HistoryTab from "../history-tab/components/HistoryTab";
import LensTab from "../lens-tab/components/LensTab";
import CloseCardPanel from "../close-card/components/CloseCardPanel";
import { closeCardModel } from "../close-card/logic/close-card";
import { lensBadge, lensSummary, shownLens } from "@/hub/review-lens/logic/lens-read";
import { useReviewLens } from "@/hub/review-lens/logic/use-review-lens";
import "../styles/card-drawer.css";

type Props = {
  project: string; workspace: string; nodeId: string; tab: CardTab; node: CanvasNode | null; parentName: string;
  editor: DrawerEditor | null; onTab: (tab: CardTab) => void; onClose: () => void;
};

/** Odpočet lease tiká sám, aby se kvůli sekundám nepřekresloval celý detail. */
function LeaseClock({ data }: { data: CardData }) {
  const lease = leaseView(data.latest, useNow(1000).getTime() / 1000, data.loadedAt);
  return <>{lease.state === "active" ? lease.label : data.latest ? data.latest.state : "—"}</>;
}

/** Jednotný detail karty: hlavička s definicí hotovo, šest záložek a jedna další akce v patičce. */
export default function CardDrawer({ project, workspace, nodeId, tab, node, parentName, editor, onTab, onClose }: Props) {
  const dialog = useRef<HTMLElement>(null);
  useDrawerFocus(dialog, onClose);
  const data = useCardData(project, workspace, nodeId);
  const sector = node?.kind === "sector";
  const available: CardTab[] = sector ? ["spec", "history"] : ["spec", "steps", "lens", "run", "review", "history"];
  const lens = useReviewLens(project, workspace, nodeId, !sector);
  const shown = available.includes(tab) ? tab : "spec";
  const steps = readSteps(data.accepted?.fields ?? null);
  const progress = steps ? stepProgress(stepRows(steps, data.stepResults, data.card?.steps?.current ?? null)) : null;
  const status = statusLine(data.card), action = nextAction(data.agent, data.card, nodeId);
  const dod = dodView({ card: data.card, steps: progress, gateStatus: data.gate?.reviewGate.status ?? null, prState: data.gate?.prState ?? null, acceptance: data.acceptance, closed: data.closed,
    eventKinds: new Set(data.events.events.map(item => item.kind)) });
  const stepsBadge = data.card?.steps ? `${data.card.steps.done}/${data.card.steps.total}` : progress ? `${progress.done}/${progress.total}` : "";
  const gateGlyph = { ready: "✓", pending: "◷", blocked: "drží" }[data.gate?.reviewGate.status ?? ""] ?? "";
  const title = node?.name ?? nodeId;
  const kind = data.card?.kind ?? (sector ? "sektor" : "karta");
  const trail = [parentName, data.card?.topoIndex != null ? `pořadí ${data.card.topoIndex + 1}` : ""].filter(Boolean).join(" · ");
  const workspaceAction = () => { onClose(); editor?.onWorkspace(); };
  const closeModel = closeCardModel(data.agent, nodeId, { pr: data.gate?.number ?? null, closed: data.closed });
  const onCloseCard = editor?.onCloseCard;
  const closeCard = onCloseCard ? async (note: string) => {
    const failure = await onCloseCard(nodeId, note);
    if (!failure) data.reload();
    return failure;
  } : null;
  return createPortal(<div className="card-drawer__overlay" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
    <section ref={dialog} className={`card-drawer${shown === "lens" ? " card-drawer--wide" : ""}`} role="dialog" aria-modal="true" aria-labelledby="card-drawer-title" tabIndex={-1}
      data-oh-view="card-drawer" data-oh-node-id={nodeId} data-oh-tab={shown} data-oh-stage={data.card?.stage ?? ""} data-oh-health={status.health}
      data-oh-accepted-head={data.agent?.heads.acceptedHead ?? ""} data-oh-execution={data.latest?.executionId ?? ""}>
      <JsonMirror id="oh-card-drawer" value={{ nodeId, tab: shown, card: data.card, status, dod, nextAction: action,
        steps: progress && { total: progress.total, done: progress.done, current: progress.current?.id ?? null },
        execution: data.latest && { executionId: data.latest.executionId, epoch: data.latest.epoch, state: data.latest.state, assignmentDigest: data.latest.assignmentDigest },
        lens: lensSummary(shownLens(lens.read)), closeCard: closeModel,
        gate: data.gate && { pr: data.gate.number, headSha: data.gate.headSha, status: data.gate.reviewGate.status, reasons: data.gate.reviewGate.reasons },
        eventsFilter: "client" }} />
      <DrawerHeader title={title} nodeId={nodeId} kind={kind} trail={trail} status={status} holder={data.latest?.state === "running" ? data.latest.owner ?? "" : ""}
        lease={data.latest?.state === "running" ? <LeaseClock data={data} /> : null} dod={dod} onClose={onClose} />
      <DrawerTabs tab={shown} available={available} onTab={onTab} badges={{
        spec: data.working ? `v${data.working.revision}` : "", steps: stepsBadge, lens: lensBadge(lens.read), run: <LeaseClock data={data} />, review: gateGlyph,
      }} />
      <div className="card-drawer__body" role="tabpanel" id={`card-drawer-panel-${shown}`} aria-labelledby={`card-drawer-tab-${shown}`}>
        {data.errors.length > 0 && <p className="card-drawer__warning" role="alert">{data.errors[0]}{data.errors.length > 1 ? ` (+${data.errors.length - 1})` : ""}</p>}
        {shown === "spec" && <SpecTab project={project} workspace={workspace} nodeId={nodeId} node={node} data={data} editor={editor} />}
        {shown === "steps" && <StepsTab data={data} onEditSteps={() => onTab("spec")} />}
        {shown === "lens" && <LensTab nodeId={nodeId} lens={lens} />}
        {shown === "run" && <RunTab project={project} workspace={workspace} nodeId={nodeId} data={data} editor={editor} onWorkspace={workspaceAction} />}
        {shown === "review" && <ReviewTab project={project} workspace={workspace} nodeId={nodeId} data={data} />}
        {shown === "history" && <HistoryTab project={project} workspace={workspace} nodeId={nodeId} events={data.events} />}
      </div>
      <CloseCardPanel model={closeModel} onCloseCard={closeCard} readOnly={editor?.readOnly ?? true} />
      <DrawerFooter action={action} busy={data.busy} onRefresh={() => { data.reload(); lens.reload(); }} />
    </section>
  </div>, document.body);
}
