import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { parseAgentState } from "@/hub/oporahub-agent-state/logic/agent-state";
import { parseGates } from "@/hub/oporahub-review-gate/logic/review-gate";
import { cardFixtureResponses } from "../logic/card-fixture";
import { cardEntry, nextAction, statusLine } from "../logic/card-header";
import { dodView } from "../logic/card-dod";
import type { CardData } from "../logic/use-card-data";
import { parseFindings } from "../review-tab/logic/review-view";
import { collectStepResults } from "../steps-tab/logic/step-status";
import { parseEventPage } from "../history-tab/logic/card-events";
import DrawerHeader from "./DrawerHeader";
import DrawerFooter from "./DrawerFooter";
import StepsTab from "../steps-tab/components/StepsTab";
import RunTab from "../run-tab/components/RunTab";
import ReviewTab from "../review-tab/components/ReviewTab";
import HistoryTab from "../history-tab/components/HistoryTab";
import SpecTab from "../spec-tab/components/SpecTab";
import LensTab from "../lens-tab/components/LensTab";
import DrawerTabs from "./DrawerTabs";
import { LENS_READ } from "@/hub/review-lens/logic/lens-fixture";
import { lensBadge, lensSummary, parseLensRead, shownLens } from "@/hub/review-lens/logic/lens-read";

const api = cardFixtureResponses() as Record<string, any>;
const agent = parseAgentState(api["/api/oporahub/agent-state"], "draft", "draft");
const card = cardEntry(agent, "card-lease");
const results = api["/api/oporahub/executions/ex0193/results"].results;
const data = {
  agent, card, context: api["/api/oporahub/changesets/context"], accepted: api["/api/oporahub/changesets/context"].acceptedDocuments[0],
  working: api["/api/oporahub/changesets/context"].documents[0], changesets: api["/api/oporahub/changesets"].items, executions: api["/api/oporahub/executions"].executions,
  latest: api["/api/oporahub/executions"].executions[0], receipts: results, stepResults: collectStepResults(results), budget: api["/api/oporahub/execution-budgets"],
  gate: parseGates(api["/api/oporahub/review-jobs/gates"])[0], findings: parseFindings(api["/api/oporahub/review-jobs"]),
  events: { ...parseEventPage(api["/api/oporahub/events"]), truncated: false, busy: false, error: "", reload: () => {} },
  loadedAt: 0, busy: false, errors: [], reload: () => {},
} as unknown as CardData;
const html = (type: unknown, props: object) => renderToStaticMarkup(createElement(type as never, props as never));

describe("card drawer rendering", () => {
  it("header carries status, holder and seven dod segments as data-oh attributes", () => {
    const markup = html(DrawerHeader, { title: "Lease a heartbeat", nodeId: "card-lease", kind: "code", trail: "Backend · pořadí 2", status: statusLine(card),
      lease: "04:12", holder: "codex-2", dod: dodView({ card }), onClose: () => {} });
    expect(markup).toContain('data-oh-close="card-drawer"');
    expect(markup.match(/data-oh-dod="/g)).toHaveLength(7);
    expect(markup).toContain('data-oh-dod="steps" data-oh-dod-state="active"');
    expect(markup).toContain("Kroky 3/7");
    expect(markup).toContain('data-oh-value="codex-2"');
  });
  it("footer shows the one next action with its actor", () => {
    const markup = html(DrawerFooter, { action: nextAction(agent, card, "card-lease"), busy: false, onRefresh: () => {} });
    expect(markup).toContain('data-oh-next-action="act_hb"');
    expect(markup).toContain('data-oh-actor="agent"');
    expect(markup).toContain("Doložit vlastní kontroly");
  });
  it("Zadání shows the diff and pending changeset", () => {
    const markup = html(SpecTab, { project: "draft", workspace: "draft", nodeId: "card-lease", node: null, data, editor: null });
    expect(markup).toContain('data-oh-spec-field="acceptance" data-oh-diff="changed"');
    expect(markup).toContain('data-oh-step-diff="s8" data-oh-diff="added"');
    expect(markup).toContain('data-oh-step-diff="s4" data-oh-diff="changed"');
    expect(markup).toContain('data-oh-changeset="cs-v4"');
  });
  it("Kroky highlights the current step and blockers", () => {
    const markup = html(StepsTab, { data, onEditSteps: () => {} });
    expect(markup).toContain('data-oh-steps-total="7" data-oh-steps-done="3" data-oh-steps-current="s4"');
    expect(markup).toContain('data-oh-plan-step="s4" data-oh-step-status="current" data-oh-step-current="true"');
    expect(markup).toContain("čeká na s4");
  });
  it("Běh shows lease, budget and step results", () => {
    const markup = html(RunTab, { project: "draft", workspace: "draft", nodeId: "card-lease", data, editor: null, onWorkspace: () => {} });
    expect(markup).toContain('data-oh-execution="ex0193" data-oh-epoch="212"');
    expect(markup).toContain('data-oh-budget="attempts" data-oh-value="1 / 3"');
    expect(markup.match(/data-oh-step-result="/g)).toHaveLength(3);
    expect(markup).toContain('data-oh-self-check="lint" data-oh-value="missing"');
  });
  it("Review & PR lists every gate reason and findings", () => {
    const markup = html(ReviewTab, { project: "draft", workspace: "draft", nodeId: "card-lease", data });
    expect(markup).toContain('data-oh-pr-number="145"');
    for (const code of ["open_important_findings", "required_checks_pending", "human_approvals_missing", "stale_against_main"]) expect(markup).toContain(`data-oh-gate-reason="${code}"`);
    expect(markup).toContain('data-oh-finding="f1" data-oh-severity="important" data-oh-finding-status="open"');
  });
  it("tabs put Lens after Kroky with the short head sha as its badge", () => {
    const read = parseLensRead(LENS_READ);
    const markup = html(DrawerTabs, { tab: "lens", available: ["spec", "steps", "lens", "run", "review", "history"], onTab: () => {},
      badges: { lens: lensBadge(read) } });
    expect(markup.indexOf('data-oh-tab="steps"')).toBeLessThan(markup.indexOf('data-oh-tab="lens"'));
    expect(markup.indexOf('data-oh-tab="lens"')).toBeLessThan(markup.indexOf('data-oh-tab="run"'));
    expect(markup).toContain(">Lens<span class=\"card-drawer__tab-badge\">373909b</span>");
    expect(lensSummary(shownLens(read))).toEqual({ kind: "pr", headSha: LENS_READ.lens.headSha, nodes: 3, edges: 2 });
  });
  it("Lens shows the header facts and lazy-loads the canvas; without a spec it explains how one arrives", () => {
    const markup = html(LensTab, { nodeId: "card-lease", lens: { read: parseLensRead(LENS_READ), busy: false, error: "", reload: () => {} } });
    expect(markup).toContain('data-oh-view="card-lens" data-oh-node-id="card-lease" data-oh-lens-kind="pr"');
    expect(markup).toContain("PR #44");
    expect(markup).toMatch(/spec \d KB · 3 části · 2 vazby/);
    expect(markup).toContain("Kopírovat spec pro agenta");
    expect(markup).toContain('data-oh-lens-loading=""');
    expect(markup).not.toContain("<svg");
    const empty = html(LensTab, { nodeId: "card-lease", lens: { read: parseLensRead({ nodeId: "card-lease", lens: null, area: null }), busy: false, error: "", reload: () => {} } });
    expect(empty).toContain('data-oh-lens-empty=""');
    expect(empty).toContain("POST /api/oporahub/review-jobs/lens");
  });
  it("Historie lists the card events newest first and says the filter is client-side", () => {
    const markup = html(HistoryTab, { project: "draft", workspace: "draft", nodeId: "card-lease", events: data.events });
    expect(markup).toContain('data-oh-events-filter="client"');
    expect(markup.indexOf("s4 zahájen")).toBeGreaterThan(-1);
    expect(markup.match(/data-oh-event="/g)).toHaveLength(7);
  });
});
