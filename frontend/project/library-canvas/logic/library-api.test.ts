import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.fn();
vi.mock("@/shared/types/logic/types", () => ({ api: (...args: unknown[]) => api(...args) }));
const { activateVersion, adoptFlow, libraryUrls, loadLibrary, placeOf, slugOf } = await import("./library-api");

describe("library API", () => {
  beforeEach(() => api.mockReset());
  it("builds the library and flow engine URLs", () => {
    expect(libraryUrls.list("agent")).toBe("/api/library?owner=agent");
    expect(libraryUrls.types()).toBe("/api/flow/node-types?kind=library_flow");
    expect(libraryUrls.projectFlows("p 1")).toBe("/api/flow/workflows?project=p+1&kind=library_flow");
  });
  it("reads folders, adopts with an optional node and activates a draft through the candidate", async () => {
    api.mockResolvedValueOnce({ owner: "human", folders: [{ id: "f" }] });
    await expect(loadLibrary("human")).resolves.toEqual([{ id: "f" }]);
    api.mockResolvedValue({});
    await adoptFlow("w", "p", "");
    expect(api).toHaveBeenLastCalledWith("/api/library/flows/w/adopt", { project: "p" });
    api.mockClear();
    await activateVersion({ id: "v", status: "draft" } as never);
    expect(api.mock.calls.map((call) => call[0])).toEqual(["/api/flow/versions/v/candidate", "/api/flow/versions/v/activate"]);
    api.mockClear();
    await activateVersion({ id: "v", status: "retired" } as never);
    expect(api.mock.calls.map((call) => call[0])).toEqual(["/api/flow/versions/v/activate"]);
  });
  it("makes slugs and tells where a flow lives", () => {
    expect(slugOf("RAG – ingest a dotaz")).toBe("rag-ingest-a-dotaz");
    expect(slugOf("!!!")).toBe("platno");
    expect(placeOf("opora:library:agent:ai-rag/rag")).toBe("agent");
    expect(placeOf("opora:project-flow:web")).toBe("project");
  });
});
