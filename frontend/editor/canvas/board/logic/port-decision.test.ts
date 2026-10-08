import { expect, it } from "vitest";
import { edgeAppearance } from "./board-model";

it("distinguishes chosen and rejected branch edges while preserving ordinary edges", () => {
  const edge = { id: "e", source: "n", target: "m", port: "block" as const, sourceBlockId: "b", sourcePortId: "p" };
  expect(edgeAppearance(edge, { status: "chosen" }).style).toEqual({ stroke: "var(--accent)", strokeWidth: 4 });
  expect(edgeAppearance(edge, { status: "rejected" }).style?.strokeDasharray).toBe("2 5");
  expect(edgeAppearance({ ...edge, port: "next" }, { status: "chosen" }).style).toBeUndefined();
});
