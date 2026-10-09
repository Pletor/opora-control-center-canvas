// Čistý model pipeline karty (port „pipeline“): etapy práce, testů, review, oprav a tří kritiků.
// Proces určuje router (orchestrátor) a každou etapu dělá vlastní relace agenta; člověk jen sleduje
// a jedním klikem přepne profil (POST /api/desktop-v3/pipeline). Šablony profilů drží jen server
// (backend/editor/agent_memory/card_pipeline.py); tady jsou popisky a ubírající zásahy člověka.
import type { DesktopState } from "@/shared/desktop-state/logic/types";
import { move, withNode } from "@/editor/workflow/blocks/logic/block-model";

export type StageKind = "work" | "test" | "review" | "fix" | "critic";
export type CriticLens = "user" | "sly" | "hacker";
export type StageStatus = "todo" | "doing" | "passed" | "failed" | "skipped";
export type PipelineProfile = "goal" | "code" | "design" | "security" | "testing" | "research" | "custom";
export type PipelineStage = {
  id: string;
  kind: StageKind;
  lens: CriticLens | "";
  title: string;
  brief: string;
  status: StageStatus;
  note: string;
  by: "human" | "agent";
  approved: boolean;
  doneBy: string;
  at: string;
  /** Opakování selhané etapy (id původní); vkládá ho server spolu s opravou. */
  retryOf?: string;
};
export type CardPipeline = { profile: PipelineProfile; items: PipelineStage[]; routedBy?: string; reason?: string };

export const KIND_LABEL: Record<StageKind, string> = { work: "práce", test: "test", review: "review", fix: "oprava", critic: "kritik" };
export const KIND_ICON: Record<StageKind, string> = { work: "⚒", test: "✓", review: "◉", fix: "↻", critic: "⚑" };
export const LENS_LABEL: Record<CriticLens, string> = { user: "hodný uživatel", sly: "vyčuraný", hacker: "hacker" };
export const STATUS_LABEL: Record<StageStatus, string> = { todo: "čeká", doing: "běží", passed: "prošlo", failed: "selhalo", skipped: "přeskočeno" };
export const PROFILE_LABEL: Record<PipelineProfile, string> = {
  goal: "GOAL", code: "Kód", design: "Design", security: "Security", testing: "Chyby", research: "Výzkum", custom: "Vlastní",
};
/** Profily, mezi kterými člověk přepíná jedním klikem; „Vlastní“ vzniká až ručními zásahy. */
export const SWITCHABLE: PipelineProfile[] = ["goal", "code", "design", "security", "testing", "research"];

export function pipelineOf(state: DesktopState, nodeId: string): CardPipeline {
  return state.nodes[nodeId]?.stages ?? { profile: "custom", items: [] };
}

/** Přepnutí profilu přepíše etapy; potvrzení chce jen tehdy, když už nějaká etapa běžela. */
export function switchNeedsConfirm(pipeline: CardPipeline): boolean {
  return pipeline.items.some((s) => s.status !== "todo");
}

const withPipeline = (nodeId: string, fn: (p: CardPipeline) => CardPipeline | null) => (state: DesktopState) =>
  withNode(state, nodeId, (n) => {
    const next = fn(n.stages ?? { profile: "custom", items: [] });
    const { stages: _dropped, ...rest } = n;
    return next && next.items.length ? { ...rest, stages: next } : rest;
  });

const mapStage = (nodeId: string, id: string, fn: (s: PipelineStage) => PipelineStage) =>
  withPipeline(nodeId, (p) => ({ ...p, items: p.items.map((s) => (s.id === id ? fn(s) : s)) }));

// Ubírající zásahy patří jen člověku (server je agentovi odmítne): odebrat, přeskládat, přeskočit, přepsat.
export const moveStage = (nodeId: string, index: number, delta: number) =>
  withPipeline(nodeId, (p) => ({ ...p, items: move(p.items, index, delta) }));
export const removeStage = (nodeId: string, id: string) =>
  withPipeline(nodeId, (p) => ({ ...p, items: p.items.filter((s) => s.id !== id) }));
export const editStage = (nodeId: string, id: string, title: string, brief: string) =>
  mapStage(nodeId, id, (s) => ({ ...s, title, brief }));
/** Přeskočení (a jeho vrácení) dělá člověk jedním klikem; ostatní stavy hlásí relace agentů. */
export const toggleSkip = (nodeId: string, id: string) =>
  mapStage(nodeId, id, (s) => (s.status === "skipped"
    ? { ...s, status: "todo", doneBy: "", at: "" }
    : { ...s, approved: true, status: "skipped", doneBy: "člověk", at: new Date().toISOString() }));

/** Etapa je vyřízená, když prošla, byla přeskočena, nebo ji nahradilo pozdější úspěšné opakování. */
function resolved(items: PipelineStage[], index: number): boolean {
  const item = items[index];
  if (item.status === "passed" || item.status === "skipped") return true;
  const root = item.retryOf ?? item.id;
  return item.status === "failed" && items.slice(index + 1).some((s) => (s.retryOf ?? s.id) === root && (s.status === "passed" || s.status === "skipped"));
}

/** Souhrn pro blok: kolik etap je vyřízených, co je na řadě a kde autonomní smyčka došla (čeká člověk). */
export function pipelineSummary(pipeline: CardPipeline) {
  const active = pipeline.items.filter((s) => s.approved);
  const open = active.map((s, i) => ({ s, i })).filter(({ i }) => !resolved(active, i));
  const stuck = open.filter(({ s, i }) => s.status === "failed"
    && !active.slice(i + 1).some((later) => (later.retryOf ?? later.id) === (s.retryOf ?? s.id) && (later.status === "todo" || later.status === "doing")));
  return {
    finished: active.length - open.length,
    total: active.length,
    current: open.find(({ s }) => s.status !== "failed")?.s ?? null,
    retries: active.filter((s) => s.retryOf).length,
    stuck: stuck.map(({ s }) => s),
  };
}
