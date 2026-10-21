import { describe, expect, it } from "vitest";
import { FormalReads, formalDetailUrl, FORMAL_ROOT } from "./formal-verification";
import { readFormalDetail, readFormalHistory, type FormalReadApi } from "./formal-verification-read";
import { formalFixture, formalScope } from "./formal-verification-fixtures";

describe("read-only formal request flows", () => {
  it("uses human-session GET initialization then exact scoped list/detail GETs", async () => {
    const record = formalFixture(), paths: string[] = [];
    const read = (async (url: string) => { paths.push(url); return url === "/api/access/ui-session" ? {} : url.startsWith(`${FORMAL_ROOT}?`) ? { requests: [record] } : record; }) as FormalReadApi;
    expect(await readFormalHistory(read, formalScope)).toEqual([record]);
    expect(await readFormalDetail(read, formalScope, record.id)).toEqual(record);
    expect(paths).toEqual(["/api/access/ui-session", `${FORMAL_ROOT}?project=project&workspace=workspace`, "/api/access/ui-session", formalDetailUrl(formalScope, record.id)]);
  });
  it("does not substitute list contents when the exact detail is missing or foreign", async () => {
    const record = formalFixture();
    const missing = (async (url: string) => { if (url === "/api/access/ui-session") return {}; throw new Error("not found"); }) as FormalReadApi;
    await expect(readFormalDetail(missing, formalScope, record.id)).rejects.toThrow("not found");
    const foreign = (async () => ({ ...record, workspace: "foreign" })) as FormalReadApi;
    await expect(readFormalDetail(foreign, formalScope, record.id)).rejects.toThrow();
    const wrongId = (async () => ({ ...record, id: "0".repeat(32) })) as FormalReadApi;
    await expect(readFormalDetail(wrongId, formalScope, record.id)).rejects.toThrow();
  });
  it.each(["scope", "selection", "refresh"])("fences late results after %s changes", async change => {
    const requests = new FormalReads();
    requests.context("project/workspace/selected/refresh0");
    const old = requests.next();
    let release!: (value: string) => void;
    let shown = "";
    const late = new Promise<string>(resolve => { release = resolve; }).then(value => { if (old()) shown = value; });
    requests.context(change === "scope" ? "other/workspace/selected/refresh0" : change === "selection" ? "project/workspace/other/refresh0" : "project/workspace/selected/refresh1");
    const current = requests.next();
    if (current()) shown = "new exact record";
    release("stale record"); await late;
    expect(shown).toBe("new exact record");
    requests.invalidate();
    expect(current()).toBe(false);
  });
});
