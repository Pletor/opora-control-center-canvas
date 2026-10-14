import { describe, expect, it } from "vitest";
import { previewOf, type ServerPlan } from "./vault-plan-preview";

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
});
