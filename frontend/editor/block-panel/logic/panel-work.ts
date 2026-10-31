// Horní sekce panelu bloku: „Práce na kartě“ (etapa, další krok, kroky, PR, kdo drží a kolik zbývá),
// „Potřebuje úsudek“ (příznaky smyčky s odkazem do detailu karty) a „Port“ (cíl a poslední zpráva).
// Čisté funkce nad stopou karty (`card-trail.ts`) a snímkem agent-state; panel jen kreslí.
import type { CardEntry } from "@/hub/oporahub-card-drawer/logic/card-header";
import type { CardTab } from "@/hub/oporahub-card-drawer/open";
import { shortReason, STAGE_WORD } from "@/editor/canvas/card-face/logic/face-labels";
import { prBadge, type PrBadge } from "@/shared/pr-badge/logic/pr-badge";
import type { StageId } from "@/hub/oporahub-agent-state/logic/agent-state";
import type { Block } from "@/shared/desktop-state/logic/types";
import type { GraphEdge } from "@/shared/types/logic/types";
import type { CardTrail, TrailJudgment, TrailPort } from "./card-trail";
import { stepMark, type StepTone } from "./trail-timeline";

export type WorkStep = { id: string; title: string; glyph: string; tone: StepTone; note: string };
export type WorkView = {
  chip: { glyph: string; word: string; tone: "run" | "ok" | "bad" | "gap" };
  stage: string; reason: string; steps: WorkStep[]; next: string | null; pr: PrBadge | null;
  holder: { name: string; until: string | null } | null; missing: string[];
};

const MISSING: Record<string, string> = {
  steps: "kroky", card_acceptance: "akceptace karty", gate_ready: "brána", merged: "PR sloučen",
  plan_written_back: "plán zapsán", journeys: "cesta ověřena", human_close: "uzavření člověkem",
};

const CHECK_GLYPH: Record<string, string> = { green: "✓", red: "✗", unknown: "?" };
/** Krátká poznámka kroku: jedna krátká kontrola jménem („npm test ✓“), jinak počty podle výsledku („kontroly: 3 ✓ · 1 ?“). */
export function checkNote(checks: { name: string; status: string }[]): string {
  if (checks.length === 1 && checks[0].name.length <= 24) return `${checks[0].name} ${CHECK_GLYPH[checks[0].status] ?? "?"}`;
  return ["green", "red", "unknown"].map((status) => [checks.filter((c) => c.status === status).length, CHECK_GLYPH[status]] as const)
    .filter(([count]) => count > 0).map(([count, glyph]) => `${count} ${glyph}`).join(" · ").replace(/^(?=.)/, "kontroly: ");
}

/** Kroky z agent-state (stav přes všechny běhy) s názvem a kontrolou z nejnovějšího běhu, který krok nese. */
export function workView(card: CardEntry | null, trail: CardTrail | null): WorkView {
  const detail = new Map<string, { title: string; status: string; note: string }>();
  for (const run of [...(trail?.runs ?? [])].reverse())
    for (const step of run.steps) detail.set(step.stepId, { title: step.title, status: step.status, note: checkNote(step.checks) });
  const current = card?.steps?.current ?? trail?.now?.stepId ?? null;
  const items = card?.steps?.items.length ? card.steps.items.map((item) => ({ id: item.id, status: item.status }))
    : [...detail].map(([id, info]) => ({ id, status: info.status }));
  const steps = items.map(({ id, status }) => {
    const open = id === current && status !== "done";
    const info = detail.get(id);
    return { id, title: info?.title || id, ...stepMark(status, open), note: open ? "další krok" : info?.note ?? "" };
  });
  const nextTitle = current ? (detail.get(current)?.title ?? "") : "";
  const stage = card ? STAGE_WORD[card.stage as StageId] ?? card.stage : "";
  const pr = card ? prBadge(card.stage, card.reason, trail?.pr ?? card.pr, false) : trail?.pr ? prBadge("", "", trail.pr, false) : null;
  return {
    chip: workChip(trail, steps), stage, reason: card ? shortReason(card.reason) : "", steps, next: current ? [current, nextTitle].filter(Boolean).join(" · ") : null, pr,
    holder: trail?.now ? { name: trail.now.owner, until: trail.now.until } : null,
    missing: (trail?.missing ?? []).map((key) => MISSING[key] ?? key),
  };
}

/** Jeden čip stavu práce: běží (někdo drží), zaseklé (dvakrát červená), hotovo (nic nechybí), jinak čeká. */
function workChip(trail: CardTrail | null, steps: WorkStep[]): WorkView["chip"] {
  if (trail?.judgment.some((item) => item.code === "red_twice")) return { glyph: "✗", word: "zaseklé", tone: "bad" };
  if (trail?.now) return { glyph: "●", word: "běží", tone: "run" };
  if (trail && !trail.missing.length && steps.length) return { glyph: "✓", word: "hotovo", tone: "ok" };
  return { glyph: "", word: "čeká", tone: "gap" };
}

/** „zbývá 18 min“ do konce držení; prošlé držení „vypršelo“, bez konce nic. */
export function remaining(until: string | null, now: number): string {
  if (!until) return "";
  const left = Date.parse(until) - now;
  if (Number.isNaN(left)) return "";
  if (left <= 0) return "vypršelo";
  const minutes = Math.ceil(left / 60_000);
  return minutes >= 120 ? `zbývá ${Math.floor(minutes / 60)} h` : `zbývá ${minutes} min`;
}

export type JudgmentView = { key: string; label: string; tone: "gold" | "bad"; where: string; reason: string; outside: string[];
  link: { tab: CardTab; text: string } };
const JUDGMENT: Record<string, { label: string; link: { tab: CardTab; text: string } }> = {
  red_twice: { label: "2× červená", link: { tab: "run", text: "Výstup kontroly v Běhu →" } },
  files_mismatch: { label: "jiné soubory", link: { tab: "review", text: "Diff v Review →" } },
  delivered_without_evidence: { label: "bez důkazu", link: { tab: "run", text: "Doručení v Běhu →" } },
  missing_summary: { label: "chybí shrnutí", link: { tab: "run", text: "Relace v Běhu →" } },
};

/** Příznak smyčky pro člověka: červeně zaseklá kontrola (`red_twice`), zlatě otázka na člověka (vše ostatní). */
export function judgmentView(item: TrailJudgment, index: number): JudgmentView {
  const known = JUDGMENT[item.code] ?? { label: item.code, link: { tab: "run" as CardTab, text: "Běh →" } };
  return { key: `${item.code}:${item.stepId ?? ""}:${index}`, label: known.label, tone: item.code === "red_twice" ? "bad" : "gold",
    where: item.stepId ?? "", reason: item.reason, outside: item.outside.slice(0, 5), link: known.link };
}

/** Odpověď člověka srdci s kontextem karty a příznaku, aby srdce vědělo, k čemu se vztahuje. */
export function heartReply(card: { id: string; name: string }, item: TrailJudgment, answer: string): string {
  const step = item.stepId ? ` u kroku ${item.stepId}` : "";
  return `Karta „${card.name}“ (${card.id}), příznak ${item.code}${step}: ${answer.trim()}`;
}

export type PortView = { key: string; label: string; target: string; message: string; handoff: string; by: string; at: string | null; source: TrailPort["source"] };

/** Port s cílem a poslední zprávou; popisek z portu bloku, ze kterého vazba vede (jinak „vazba“). */
export function portViews(ports: TrailPort[], edges: GraphEdge[], blocks: Block[]): PortView[] {
  return ports.map((port) => {
    const edge = edges.find((item) => item.id === port.edgeId);
    const block = edge?.sourceBlockId ? blocks.find((item) => item.id === edge.sourceBlockId) : undefined;
    const label = block?.ports?.find((item) => item.id === edge?.sourcePortId)?.label ?? "vazba";
    return { key: port.edgeId, label, target: port.targetName || port.targetId, message: port.summary, handoff: port.handoff,
      by: port.by, at: port.updatedAt, source: port.source };
  });
}
