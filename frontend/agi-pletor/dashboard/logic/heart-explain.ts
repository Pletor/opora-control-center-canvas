import { list, rec, str, unavailable } from "./view-common";

export type Phase = { id: string; label: string; seconds: string; percent: number };
export type BatchView = { at: string; headline: string; status: string; phases: Phase[]; slowest: string[]; failures: string[]; truncated: boolean };
export type StopView = { id: string; label: string; active: boolean; detail: string; lever: string };
export type PipelineRun = { run: string; status: string; line: string };
export type QueueRow = { type: string; ref: string; workspace: string; dueIn: string };
export type ExplainView = {
  now: { sentence: string; state: string; error: string };
  stops: { rows: StopView[]; error: string };
  pipeline: { runs: PipelineRun[]; error: string };
  batches: { rows: BatchView[]; error: string };
  queue: { rows: QueueRow[]; error: string };
};

const seconds = (ms: unknown) => (typeof ms === "number" && Number.isFinite(ms) ? `${Math.round(ms / 1000)} s` : "");

/** Odpověď `GET /api/pletor/heart/explain` → pohled; každá sekce nese vlastní `error`, ostatní dál fungují. */
export function explainView(raw: unknown): ExplainView {
  const root = rec(raw);
  const now = rec(root.now);
  const stops = list(root.stops).map((item) => {
    const s = rec(item);
    return { id: str(s.id), label: str(s.label) || str(s.id), active: s.active === true, detail: str(s.detail), lever: str(s.lever) };
  });
  const runs = list(root.pipeline).map((item) => {
    const r = rec(item);
    const line = list(r.nodes).map((n) => `${str(rec(n).label) || str(rec(n).node)} ${seconds(rec(n).ms) || "běží"}`).join(" → ");
    return { run: str(r.run), status: str(r.status), line };
  });
  const batches = list(root.batches).map((item) => {
    const b = rec(item);
    return {
      at: str(b.at), headline: str(b.headline) || str(b.summary), status: str(b.status), truncated: b.truncated === true,
      phases: list(b.phases).map((p) => ({ id: str(rec(p).id), label: str(rec(p).label), seconds: seconds(rec(p).ms), percent: Math.max(0, Math.min(100, Math.round(Number(rec(p).share) * 100) || 0)) })),
      slowest: list(b.slowest).map((x) => `${str(rec(x).tool)} ${seconds(rec(x).ms)} (${str(rec(x).category)})`),
      failures: list(b.failures).map((x) => `${str(rec(x).tool)}: ${str(rec(x).error)}`),
    };
  });
  const queue = list(root.queue).map((item) => {
    const q = rec(item);
    return { type: str(q.type), ref: str(q.ref), workspace: str(q.workspace), dueIn: typeof q.dueInS === "number" ? String(Math.round(q.dueInS)) : "" };
  });
  return {
    now: { sentence: str(now.sentence), state: str(now.state), error: unavailable(root.now) },
    stops: { rows: [...stops.filter((s) => s.active), ...stops.filter((s) => !s.active)], error: unavailable(root.stops) },
    pipeline: { runs, error: unavailable(root.pipeline) },
    batches: { rows: batches.reverse(), error: unavailable(root.batches) },
    queue: { rows: queue, error: unavailable(root.queue) },
  };
}
