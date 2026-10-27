import { afterEach, describe, expect, it, vi } from "vitest";
import { emptyStudioModel } from "./model-types";
import { normalizeStudioModel, saveStudioModel, studioModelUrl } from "./studio-model-api";

const json = (status: number, body: unknown) => Promise.resolve({ status, ok: status < 400, text: () => Promise.resolve(JSON.stringify(body)), headers: new Headers() });

describe("studio model API", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("adresa nese projekt a doménu", () => {
    expect(studioModelUrl("p 1", "d/1")).toBe("/api/studio/model?project=p+1&domain=d%2F1");
  });

  it("neznámý tvar nebo cizí doména = prázdný model s revizí 0", () => {
    expect(normalizeStudioModel(null, "d")).toEqual(emptyStudioModel("d"));
    expect(normalizeStudioModel({ ...emptyStudioModel("jina"), revision: 3 }, "d")).toEqual(emptyStudioModel("d"));
    expect(normalizeStudioModel({ ...emptyStudioModel("d"), revision: 1.5 }, "d")).toEqual(emptyStudioModel("d"));
    const saved = { ...emptyStudioModel("d"), revision: 4, updatedAt: "2026-10-27T10:00:00Z" };
    expect(normalizeStudioModel(saved, "d")).toEqual(saved);
  });

  it("uložení posílá PUT s revizí a 409 hlásí jako konflikt", async () => {
    const calls: { url: string; init: RequestInit }[] = [];
    const responses = [json(200, { ...emptyStudioModel("d"), revision: 1 }), json(409, { error: "Model mezitím změnil někdo jiný." })];
    vi.stubGlobal("fetch", (url: string, init: RequestInit) => {
      calls.push({ url, init });
      if (!url.startsWith("/api/studio/model")) return json(200, {});
      return responses.shift()!;
    });
    const first = await saveStudioModel("p", "d", emptyStudioModel("d"));
    expect(first).toEqual({ kind: "saved", model: { ...emptyStudioModel("d"), revision: 1 } });
    const put = calls.find((c) => c.url.startsWith("/api/studio/model"))!;
    expect(put.init.method).toBe("PUT");
    expect(JSON.parse(put.init.body as string)).toMatchObject({ schema: "opora.studio-model/1", domainId: "d", revision: 0 });
    expect(await saveStudioModel("p", "d", { ...emptyStudioModel("d"), revision: 0 })).toEqual({ kind: "conflict", message: "Model mezitím změnil někdo jiný." });
  });
});
