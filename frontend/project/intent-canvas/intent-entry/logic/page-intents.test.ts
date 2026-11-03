import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.fn();
vi.mock("@/shared/types/logic/types", () => ({ api: (...args: unknown[]) => api(...args) }));
const { intentBadge, loadPageIntents, pageIntentsUrl, parsePageIntents } = await import("./page-intents");

const MOCK = { pages: [
  { pageId: "home", state: "approved", workflowId: "w1", activeN: 2, doneCount: 3 },
  { pageId: "kontakt", state: "pending", workflowId: "w2", candidateN: 1, doneCount: 0 },
  { pageId: "o-nas", state: "stale", workflowId: "w3", activeN: 1, doneCount: 1 },
  { pageId: "blog", state: "none", doneCount: 0 },
  { pageId: "divny", state: "unknown", doneCount: 0 },
] };

describe("page intent states for the Záměr badge", () => {
  beforeEach(() => api.mockReset());
  it("reads the {pages: [...]} envelope and drops rows it does not understand", () => {
    const intents = parsePageIntents(MOCK);
    expect([...intents.keys()]).toEqual(["home", "kontakt", "o-nas", "blog"]);
    expect(parsePageIntents({ detail: "Not Found" }).size).toBe(0);
    expect(pageIntentsUrl("p 1")).toBe("/api/flow/page-intents?project=p+1");
  });
  it("labels the badge in Czech by state", () => {
    const intents = parsePageIntents(MOCK);
    expect(["home", "kontakt", "o-nas", "blog"].map((id) => intentBadge(intents.get(id))?.label)).toEqual(["schválený v2", "čeká", "zastaralý", "bez záměru"]);
    expect(intentBadge(intents.get("home"))?.title).toBe("3 kritérií hotovo");
    expect(intentBadge(undefined)).toBeNull();
  });
  it("turns a missing endpoint (404) into an unknown state: no badge, button stays", async () => {
    api.mockRejectedValueOnce(Object.assign(new Error("Not Found"), { status: 404 }));
    await expect(loadPageIntents("p")).resolves.toBeNull();
    api.mockResolvedValueOnce(MOCK);
    expect((await loadPageIntents("p"))?.get("kontakt")?.state).toBe("pending");
  });
});
