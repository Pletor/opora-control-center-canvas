import { describe, expect, it } from "vitest";
import { keyAction, nextInDirection } from "./studio-keys";

const cards = [{ id: "a", x: 0, y: 0 }, { id: "b", x: 380, y: 0 }, { id: "c", x: 0, y: 214 }, { id: "d", x: 380, y: 30 }];

describe("studio keys", () => {
  it("maps keys to actions", () => {
    expect(keyAction("ArrowRight")).toEqual({ kind: "move", direction: "right" });
    expect(keyAction("Enter")).toEqual({ kind: "enter" });
    expect(keyAction("Backspace")).toEqual({ kind: "up" });
    expect(keyAction("Escape")).toEqual({ kind: "clear" });
    expect(keyAction("a")).toBeNull();
  });

  it("moves to the nearest card in a direction and stays when nothing is there", () => {
    expect(nextInDirection(cards, null, "down")).toBe("a");
    expect(nextInDirection(cards, "a", "right")).toBe("b");
    expect(nextInDirection(cards, "a", "down")).toBe("c");
    expect(nextInDirection(cards, "b", "down")).toBe("d");
    expect(nextInDirection(cards, "a", "left")).toBe("a");
    expect(nextInDirection([], null, "up")).toBeNull();
  });
});
