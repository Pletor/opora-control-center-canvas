import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { agentStateFixture } from "@/hub/oporahub-agent-state/logic/fixtures";
import OporaHubOverview from "./OporaHubOverview";
import { LEGACY_LINKS } from "./LegacyLinks";

const render = (tab: "overview" | "agents", state = agentStateFixture()) => renderToStaticMarkup(createElement(OporaHubOverview, {
  agent: { state, etag: '"v1"', error: "", loadedAt: 1 }, tab, onTab: vi.fn(), onOpenCard: vi.fn(), open: vi.fn(), onRefresh: vi.fn() }));

describe("OporaHub overview reads one agent-state document", () => {
  it("renders the ten-stage loop with data-oh contract attributes", () => {
    const html = render("overview");
    expect(html.match(/data-oh-stage="/g)).toHaveLength(10);
    expect(html).toContain('data-oh-stage="work" data-oh-health="blocking" data-oh-reason="lease_past_deadline"');
    expect(html).toContain('data-oh-view="overview"');
    expect(html).toContain(`data-oh-accepted-head="${"a".repeat(40)}"`);
    expect(html).toContain('data-oh-etag="&quot;v1&quot;"');
    expect(html).toContain('data-oh-decision="dec_1" data-oh-action-id="act_1"');
    expect(html).toContain('data-oh-gap="pull_request_link"');
  });
  it("mirrors the exact document in a JSON script for agents", () => {
    const html = render("overview");
    const json = html.match(/<script type="application\/json" id="oh-agent-state">(.*?)<\/script>/)?.[1] ?? "";
    expect(JSON.parse(json)).toEqual(agentStateFixture());
  });
  it("renders the agent view with action rows carrying id and status", () => {
    const html = render("agents");
    expect(html).toContain('data-oh-view="agent"');
    expect(html).toContain('data-oh-action-id="act_4" data-oh-action-status="ready" data-oh-verb="claim"');
    expect(html).toContain('data-oh-block-reason="human_only"');
    expect(html).toContain("kopírovat JSON");
    expect(html).toContain('data-oh-field="contextVersion"');
  });
  it("keeps every legacy drawer reachable from the footer", () => {
    const html = render("overview");
    for (const link of LEGACY_LINKS) expect(html).toContain(`data-oh-detail="${link.kind}"`);
    expect(html).toContain("Formální podklady");
    expect(html).toContain("Změny obsahu");
  });
  it("says it is loading instead of inventing a state", () => {
    const html = renderToStaticMarkup(createElement(OporaHubOverview, { agent: { state: null, etag: "", error: "", loadedAt: 0 },
      tab: "overview", onTab: vi.fn(), onOpenCard: vi.fn(), open: vi.fn(), onRefresh: vi.fn() }));
    expect(html).toContain("Načítám stav OporaHubu");
    expect(html).not.toContain("data-oh-stage");
    expect(html).toContain('id="oh-agent-state">null</script>');
  });
});
