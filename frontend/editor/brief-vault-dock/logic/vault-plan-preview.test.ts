import { describe, expect, it } from "vitest";
import { ApiError } from "@/shared/types/logic/types";
import { planBlocker, previewOf, type ServerPlan } from "./vault-plan-preview";

describe("vault plan preview", () => {
  it("lists cards, counts their blocks and names only the new structure", () => {
    const result: ServerPlan = {
      plan: {
        nodes: [
          { ref: "a1", kind: "area", name: "Logika", parent: "@s1" },
          { ref: "s1", kind: "sector", name: "Backend", parent: "a1" },
          { ref: "f1", kind: "node", name: "[task] 3.12 Chunks", parent: "s1", blocks: [{ title: "3.12.1" }, { title: "Komponenta" }] },
          { ref: "f2", kind: "node", name: "[task] 3.15 Metadata", parent: "@sector" },
        ],
        edges: [{ from: "f1", to: "f2", port: "next" }],
      },
      summary: "Přidá 1 oblast, 1 sektor, 2 karty, 2 bloky.", hash: "h", skipped: 0, digest: "d",
    };
    const preview = previewOf(result);
    expect(preview.cards.map((card) => card.ref)).toEqual(["f1", "f2"]);
    expect(preview.blocks).toBe(2);
    expect(preview.structure).toEqual(["oblast Logika", "sektor Backend"]);
  });

  it("groups the structured 409 fragments by reason without parsing the error text", () => {
    const error = new ApiError("Schránka zadání: disciplína je pro strukturu povinná; …", 409, {
      error: "…",
      fragments: [
        { id: "old1", title: "Staré", reason: "no-discipline" },
        { id: "f_12", title: "3.12 Chunks (v2)", reason: "no-synthesized" },
        { id: "a-9", title: "", reason: "no-synthesized" },
        { id: "x", title: "Jiné", reason: "future-reason" },
        { title: "bez id" },
      ],
    });
    const blocker = planBlocker(error);
    expect(blocker?.groups.map((group) => group.reason)).toEqual(["no-discipline", "no-synthesized", "future-reason"]);
    expect(blocker?.groups[1].fragments).toEqual([{ id: "f_12", title: "3.12 Chunks (v2)" }, { id: "a-9", title: "a-9" }]);
    expect(blocker?.groups[0].text).toContain("nemají disciplínu");
    expect(blocker?.groups[2].text).toBe("Tyto fragmenty brání složení plánu.");
  });

  it("other errors stay plain text", () => {
    expect(planBlocker(new Error("Schránka zadání: chybí platná brána synthesized (done mikrokroku) u: „X“ (x)."))).toBeNull();
    expect(planBlocker(new ApiError("main je pouze pro čtení.", 409, { error: "main je pouze pro čtení." }))).toBeNull();
    expect(planBlocker(new ApiError("špatně", 400, { error: "špatně", fragments: [{ id: "x" }] }))).toBeNull();
  });
});
