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
import { plural, stepMark, type StepTone } from "./trail-timeline";

export type WorkStep = { id: string; title: string; glyph: string; tone: StepTone; note: string };
export type WorkView = {
  chip: { glyph: string; word: string; tone: "run" | "ok" | "bad" | "gap" };
  /** Text vedle čipu: „implementace · krok 2 ze 3“, „3/3 kroků“, „s2 · 2× červená“, „na kartu …“. */
  line: string;
  stage: string; reason: string; steps: WorkStep[]; next: string | null; pr: PrBadge | null;
  /** Počet různých commitů ve stopě („2 commity“ u PR); prázdné, když žádný není. */
  commits: string;
  holder: { name: string; until: string | null } | null;
  /** Kdy kartu dělník naposled uvolnil (`lease.released` ve stopě), jen když ji nikdo nedrží. */
  released: string | null;
  /** Ještě nikdo nepracoval: žádná relace a nikdo nedrží. */
  untouched: boolean;
  missing: string[];
};

const MISSING: Record<string, string> = {
  steps: "kroky", card_acceptance: "akceptace karty", gate_ready: "brána", merged: "PR sloučen",
  plan_written_back: "plán zapsán", journeys: "cesta ověřena", human_close: "uzavření člověkem",
};

const short = (name: string) => (name.length <= 24 ? name : name.slice(0, 23).trimEnd() + "…");
/**
 * Krátká poznámka kroku vpravo: první červená kontrola jménem („npm test ✗“), jinak jediná zelená jménem
 * („npm test ✓“) nebo počet zelených. Bez známého výsledku kontrol krátký commit (krok doložený commitem),
 * jinak nic: „kontroly: 2 ?“ člověku nic neřekne.
 */
export function checkNote(checks: { name: string; status: string }[], commits: string[] = []): string {
  const red = checks.find((check) => check.status === "red");
  if (red) return `${short(red.name)} ✗`;
  const green = checks.filter((check) => check.status === "green");
  if (green.length === 1) return `${short(green[0].name)} ✓`;
  if (green.length > 1) return `${green.length} ✓`;
  return commits[0]?.slice(0, 7) ?? "";
}

/** „ze 3“, „z 5“: předložka podle vyslovení čísla (dvou, tří, čtyř, sedmi, sta). */
export const ofCount = (total: number) => (/^(2|3|4|7|17|7\d|1\d\d)$/.test(String(total)) ? `ze ${total}` : `z ${total}`);

/** Kroky z agent-state (stav přes všechny běhy) s názvem a kontrolou z nejnovějšího běhu, který krok nese. */
export function workView(card: CardEntry | null, trail: CardTrail | null, context: { waitingFor?: string[] } = {}): WorkView {
  const detail = new Map<string, { title: string; status: string; note: string }>();
  for (const run of [...(trail?.runs ?? [])].reverse())
    for (const step of run.steps) detail.set(step.stepId, { title: step.title, status: step.status, note: checkNote(step.checks, step.commits) });
  const stuck = new Set((trail?.judgment ?? []).filter((item) => item.code === "red_twice").map((item) => item.stepId ?? ""));
  const current = card?.steps?.current ?? trail?.now?.stepId ?? null;
  const items = card?.steps?.items.length ? card.steps.items.map((item) => ({ id: item.id, status: item.status }))
    : [...detail].map(([id, info]) => ({ id, status: info.status }));
  const steps = items.map(({ id, status }) => {
    const open = id === current && status !== "done";
    const info = detail.get(id);
    if (stuck.has(id)) return { id, title: info?.title || id, glyph: "✗", tone: "bad" as const, note: "2× červená" };
    return { id, title: info?.title || id, ...stepMark(status, open), note: open ? "další krok" : info?.note ?? "" };
  });
  const nextTitle = current ? (detail.get(current)?.title ?? "") : "";
  const stage = card ? STAGE_WORD[card.stage as StageId] ?? card.stage : "";
  const pr = card ? prBadge(card.stage, card.reason, trail?.pr ?? card.pr, false) : trail?.pr ? prBadge("", "", trail.pr, false) : null;
  const reason = card ? shortReason(card.reason) : "";
  const chip = workChip(trail, steps);
  const commits = new Set((trail?.runs ?? []).flatMap((run) => run.steps.flatMap((step) => step.commits)));
  const released = trail && !trail.now ? trail.recent.find((event) => event.kind === "lease.released")?.at ?? null : null;
  return {
    chip, line: statusLine(chip, steps, stage, reason, [...stuck][0] ?? "", context.waitingFor ?? []),
    stage, reason, steps, next: current ? [current, nextTitle].filter(Boolean).join(" · ") : null, pr,
    commits: commits.size ? plural(commits.size, "commit", "commity", "commitů") : "",
    holder: trail?.now ? { name: trail.now.owner, until: trail.now.until } : null, released,
    untouched: !trail?.now && !trail?.runs.length,
    missing: (trail?.missing ?? []).map((key) => MISSING[key] ?? key),
  };
}

/** Jedna věta vedle čipu: kde práce je (běží), čím skončila (hotovo), co ji zasekává, nebo na co karta čeká. */
function statusLine(chip: WorkView["chip"], steps: WorkStep[], stage: string, reason: string, stuckStep: string, waitingFor: string[]): string {
  const done = steps.filter((step) => step.tone === "done").length;
  if (chip.tone === "bad") return [stuckStep, "2× červená"].filter(Boolean).join(" · ");
  if (chip.tone === "run" && steps.length) {
    const at = steps.findIndex((step) => step.tone === "cur");
    return [stage, `krok ${at >= 0 ? at + 1 : Math.min(done + 1, steps.length)} ${ofCount(steps.length)}`].filter(Boolean).join(" · ");
  }
  if (chip.tone === "ok") return steps.length ? `${done}/${steps.length} kroků` : "";
  if (waitingFor.length) return `na ${waitingFor.length === 1 ? "kartu" : "karty"} ${waitingFor.join(", ")}`;
  return [stage, reason].filter(Boolean).join(" · ");
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
  /** Úsudek srdce k příznaku (řádek ✦). `card-trail` ho dnes nenese, proto je prázdný; místo v panelu je připravené. */
  heart: string;
  link: { tab: CardTab; text: string } };
const JUDGMENT: Record<string, { label: string; link: { tab: CardTab; text: string } }> = {
  red_twice: { label: "2× červená", link: { tab: "run", text: "Výstup kontroly →" } },
  files_mismatch: { label: "jiné soubory", link: { tab: "review", text: "Diff v Review →" } },
  delivered_without_evidence: { label: "bez důkazu", link: { tab: "run", text: "Doručení v Běhu →" } },
  missing_summary: { label: "chybí shrnutí", link: { tab: "run", text: "Relace v Běhu →" } },
};

/** Příznak smyčky pro člověka: červeně zaseklá kontrola (`red_twice`), zlatě otázka na člověka (vše ostatní). */
export function judgmentView(item: TrailJudgment, index: number): JudgmentView {
  const known = JUDGMENT[item.code] ?? { label: item.code, link: { tab: "run" as CardTab, text: "Běh →" } };
  return { key: `${item.code}:${item.stepId ?? ""}:${index}`, label: known.label, tone: item.code === "red_twice" ? "bad" : "gold",
    where: item.stepId ?? "", reason: item.reason, outside: item.outside.slice(0, 5), heart: "", link: known.link };
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
