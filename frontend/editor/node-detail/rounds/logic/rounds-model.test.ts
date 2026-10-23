import { describe, expect, it } from "vitest";
import { cardView } from "@/editor/canvas/node-card/logic/card-model";
import { roundNumber } from "@/editor/node-detail/rounds/logic/rounds-model";
import { emptyNodeWorkflow } from "@/shared/desktop-state/logic/types";
import type { CanvasNode } from "@/shared/types/logic/types";

describe("zbytek kol karty", () => {
  it("karta bez kola je vždy v kole 1", () => {
    expect(roundNumber(undefined)).toBe(1);
    const node = { id: "c1", parentId: null, kind: "node", name: "Karta", purpose: "", x: 0, y: 0 } as unknown as CanvasNode;
    expect(cardView(node, emptyNodeWorkflow(), 0).round).toBe(1);
  });
});
