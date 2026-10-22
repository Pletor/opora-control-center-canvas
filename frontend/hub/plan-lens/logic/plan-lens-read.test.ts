import { describe, expect, it } from "vitest";
import { parseSpec, renderStage } from "@/hub/review-lens/logic/stage-render";
import { stagesOf } from "@/hub/review-lens/logic/walkthrough";
import { PLAN_LENS_RESPONSE, PLAN_SPEC } from "./plan-lens-fixture";
import { IDLE, parsePlanLens, planLensReducer, planLensUrl, readPlanLens, type PlanLensState } from "./plan-lens-read";

const reply = (status: number, body = "", headers: Record<string, string> = {}) => async () => new Response(status === 304 ? null : body, { status, headers });
const signal = () => new AbortController().signal;

describe("plan lens read", () => {
  it("builds the project and the area URL", () => {
    expect(planLensUrl("p", "w", null)).toBe("/api/oporahub/plan-lens?project=p&workspace=w");
    expect(planLensUrl("p", "w", "area 1")).toBe("/api/oporahub/plan-lens?project=p&workspace=w&area=area+1");
  });
  it("parses the envelope strictly", () => {
    const lens = parsePlanLens(PLAN_LENS_RESPONSE);
    expect(lens).toMatchObject({ area: "area-login", digest: "sha256:5f1c0d9e", stats: { cards: 3, planned: 1 }, graphify: { available: true } });
    expect(() => parsePlanLens({ ...PLAN_LENS_RESPONSE, kind: "pr" })).toThrow();
    expect(() => parsePlanLens({ ...PLAN_LENS_RESPONSE, spec: { kind: "patch" } })).toThrow();
    expect(() => parsePlanLens({ ...PLAN_LENS_RESPONSE, stats: { ...PLAN_LENS_RESPONSE.stats, cards: -1 } })).toThrow();
    expect(parsePlanLens({ ...PLAN_LENS_RESPONSE, area: null, graphify: null })).toMatchObject({ area: null, graphify: { available: false, sourceRevision: null } });
  });
  it("turns each response into one state event and sends the ETag on refresh", async () => {
    let sent: HeadersInit | undefined;
    const ok = await readPlanLens("/u", "", signal(), async (_url, init) => { sent = init.headers; return new Response(JSON.stringify(PLAN_LENS_RESPONSE), { status: 200, headers: { ETag: '"d1"' } }); });
    expect(ok).toMatchObject({ type: "ok", etag: '"d1"' });
    expect(sent).toEqual({});
    await readPlanLens("/u", '"d1"', signal(), async (_url, init) => { sent = init.headers; return new Response(null, { status: 304 }); });
    expect(sent).toEqual({ "If-None-Match": '"d1"' });
    expect(await readPlanLens("/u", '"d1"', signal(), reply(304))).toEqual({ type: "same" });
    expect(await readPlanLens("/u", "", signal(), reply(404, "{}"))).toEqual({ type: "unavailable" });
    expect(await readPlanLens("/u", "", signal(), reply(500, "{}"))).toMatchObject({ type: "error", message: expect.stringContaining("500") });
    expect(await readPlanLens("/u", "", signal(), reply(200, "{\"kind\":\"plan\"}"))).toMatchObject({ type: "error" });
    expect(await readPlanLens("/u", "", signal(), async () => { throw new TypeError("offline"); })).toEqual({ type: "error", message: "offline" });
  });
  it("walks loading → ok → 304 keep → error keeps data → 404 calm unavailable", () => {
    const data = parsePlanLens(PLAN_LENS_RESPONSE);
    let state: PlanLensState = planLensReducer(IDLE, { type: "start" });
    expect(state.status).toBe("loading");
    state = planLensReducer(state, { type: "ok", data, etag: '"d1"' });
    expect(state).toMatchObject({ status: "ok", etag: '"d1"' });
    state = planLensReducer(planLensReducer(state, { type: "start" }), { type: "same" });
    expect(state).toMatchObject({ status: "ok", data, etag: '"d1"' });
    state = planLensReducer(state, { type: "error", message: "HTTP 500" });
    expect(state).toMatchObject({ status: "error", data, error: "HTTP 500" });
    expect(planLensReducer(state, { type: "unavailable" })).toEqual({ ...IDLE, status: "unavailable" });
    expect(planLensReducer(IDLE, { type: "same" }).status).toBe("error");
    expect(planLensReducer(state, { type: "reset" })).toBe(IDLE);
  });
  it("ships a fixture that passes the PR Lens schema and draws", () => {
    const parsed = parseSpec(PLAN_SPEC);
    expect(parsed.error).toBe("");
    const stage = stagesOf(parsed.doc!)[0];
    const drawn = renderStage(parsed.doc!, stage, "dark");
    expect("svg" in drawn && drawn.svg.startsWith("<svg")).toBe(true);
  });
});
