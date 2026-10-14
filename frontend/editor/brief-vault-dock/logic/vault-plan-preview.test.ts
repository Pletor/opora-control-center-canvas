import { describe, expect, it } from "vitest";
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

  it("turns a 409 about missing discipline or synthesized gate into a list of fragments to open", () => {
    const missing = planBlocker("Schránka zadání: chybí platná brána synthesized (done mikrokroku) u: „3.12 Chunks (v2)“ (f_12), „Index“ (a-9) a dalších 3.");
    expect(missing).toMatchObject({ reason: "unsynthesized", more: 3 });
    expect(missing?.fragments).toEqual([{ id: "f_12", title: "3.12 Chunks (v2)" }, { id: "a-9", title: "Index" }]);
    expect(planBlocker("Schránka zadání: disciplína je pro strukturu povinná; nezařazené fragmenty: „Staré“ (old1).")?.reason).toBe("unassigned");
    expect(planBlocker("Schránka zadání: main je pouze pro čtení.")).toBeNull();
  });
});
