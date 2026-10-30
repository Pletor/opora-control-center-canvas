import { describe, expect, it } from "vitest";
import { decideMilestone, decisionError, intakeUrl, readIntake } from "./intake-api";

describe("API pohledu Požadavky a plán", () => {
  it("čte /api/intake se zakódovaným projektem a prostorem a ověří odpověď", async () => {
    const urls: string[] = [];
    const call = (async (url: string) => { urls.push(url); return { areas: [], unassigned: [], entries: [], pending: 0, duplicates: 0 }; }) as never;
    await readIntake("p&1", "main", call);
    expect(urls).toEqual(["/api/intake?project=p%261&workspace=main"]);
    expect(intakeUrl("p", "w")).toBe("/api/intake?project=p&workspace=w");
    await expect(readIntake("p", "w", (async () => ({ nope: 1 })) as never)).rejects.toThrow("neplatnou odpověď");
  });

  it("rozhodnutí posílá přesné tělo {project, workspace, milestoneId, action}", async () => {
    const calls: [string, object | undefined][] = [];
    const call = (async (url: string, body?: object) => { calls.push([url, body]); return { id: "ms_1", status: "active", superseded: null }; }) as never;
    await decideMilestone("p", "w", "ms_1", "activate", call);
    expect(calls).toEqual([["/api/intake/milestone", { project: "p", workspace: "w", milestoneId: "ms_1", action: "activate" }]]);
  });

  it("chyba je česká věta s textem serveru", () => {
    expect(decisionError("reject", new Error("Milník je active, rozhodnout jde jen o návrh.")))
      .toBe("Milník se nepodařilo zamítnout: Milník je active, rozhodnout jde jen o návrh.");
    expect(decisionError("activate", "x")).toBe("Milník se nepodařilo aktivovat: neznámá chyba");
  });
});
