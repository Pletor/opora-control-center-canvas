import { isCount, isObject, isText } from "@/hub/oporahub-mirror/logic/hub-read";

// Doklady po krocích plánu na položce brány (`evidence.steps`, docs/oporahub-review-jobs.md, „Doklady kroků“).
// Jen ukazuje, co běhy nahlásily ke krokům přiřazeného plánu; stav brány nemění.
export type StepStatus = "done" | "blocked" | "missing";
export type StepEvidenceItem = {
  id: string; title: string; status: StepStatus; reported: string | null; executionId: string | null;
  source: "result" | "checkpoint" | null; at: string | null; evidenced: boolean;
  evidence: { checks: string[]; commits: string[]; notes: string };
};
export type StepEvidence = {
  items: StepEvidenceItem[]; decisions: number;
  verdict: { status: "evidenced" | "incomplete"; total: number; done: number; blocked: string[]; missing: string[]; withoutEvidence: string[] };
};

const texts = (value: unknown): string[] => Array.isArray(value) ? value.filter(item => isText(item)) as string[] : [];
const opt = (value: unknown) => isText(value) ? value : null;
const STATUSES: StepStatus[] = ["done", "blocked", "missing"];

function item(raw: unknown): StepEvidenceItem | null {
  if (!isObject(raw) || !isText(raw.id) || !STATUSES.includes(raw.status as StepStatus)) return null;
  const ev = isObject(raw.evidence) ? raw.evidence : {};
  return { id: raw.id, title: isText(raw.title) ? raw.title : "", status: raw.status as StepStatus, reported: opt(raw.reported),
    executionId: opt(raw.executionId), source: raw.source === "result" || raw.source === "checkpoint" ? raw.source : null,
    at: opt(raw.at), evidenced: raw.evidenced === true,
    evidence: { checks: texts(ev.checks), commits: texts(ev.commits), notes: isText(ev.notes) ? ev.notes : "" } };
}

/** Neplatný nebo chybějící blok → null (brána bez kroků plánu). */
export function parseStepEvidence(raw: unknown): StepEvidence | null {
  if (!isObject(raw) || !Array.isArray(raw.items) || !isObject(raw.verdict)) return null;
  const v = raw.verdict, items = raw.items.map(item).filter((entry): entry is StepEvidenceItem => entry !== null);
  return { items, decisions: isCount(raw.decisions) ? raw.decisions : 0, verdict: {
    status: v.status === "evidenced" ? "evidenced" : "incomplete", total: isCount(v.total) ? v.total : items.length,
    done: isCount(v.done) ? v.done : 0, blocked: texts(v.blocked), missing: texts(v.missing), withoutEvidence: texts(v.withoutEvidence) } };
}

export type StepEvidenceView = {
  ok: boolean; headline: string; flags: string[];
  rows: { id: string; title: string; glyph: string; status: StepStatus; detail: string; flagged: boolean }[];
};
const GLYPH: Record<StepStatus, string> = { done: "✓", blocked: "✕", missing: "–" };

/** Řádek na krok: stav, kontroly, commity, poznámka; bez dokladu je řádek označený. */
export function stepEvidenceView(steps: StepEvidence): StepEvidenceView {
  const v = steps.verdict, without = new Set(v.withoutEvidence);
  const flags = [v.blocked.length ? `zablokováno: ${v.blocked.join(", ")}` : "", v.missing.length ? `nenahlášeno: ${v.missing.join(", ")}` : "",
    v.withoutEvidence.length ? `bez dokladu: ${v.withoutEvidence.join(", ")}` : ""].filter(Boolean);
  return {
    ok: v.status === "evidenced", flags,
    headline: `${v.done}/${v.total} kroků hotovo${v.status === "evidenced" ? " a doloženo" : ""}`
      + (steps.decisions ? ` · ${steps.decisions} rozhodnutí` : ""),
    rows: steps.items.map(step => ({
      id: step.id, title: step.title || step.id, glyph: GLYPH[step.status], status: step.status, flagged: without.has(step.id) || step.status !== "done",
      detail: [step.evidence.checks.length ? `kontroly: ${step.evidence.checks.join(", ")}` : "",
        step.evidence.commits.length ? `commity: ${step.evidence.commits.map(sha => sha.slice(0, 7)).join(", ")}` : "",
        step.evidence.notes.trim()].filter(Boolean).join(" · ") || (step.status === "missing" ? "krok nikdo nenahlásil" : "bez dokladu"),
    })),
  };
}
