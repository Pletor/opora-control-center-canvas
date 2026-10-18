import { describe, expect, it } from "vitest";
import { nextWaiting } from "./next-waiting";

const queue = [{ id: "a" }, { id: "b" }, { id: "c" }];

describe("nextWaiting", () => {
  it("bez čekajících nic", () => {
    expect(nextWaiting([], null)).toBeNull();
    expect(nextWaiting([], "a")).toBeNull();
  });

  it("první klik vybere nejstaršího", () => {
    expect(nextWaiting(queue, null)).toBe("a");
  });

  it("další klik jde za vybraného a za posledním cyklí na začátek", () => {
    expect(nextWaiting(queue, "a")).toBe("b");
    expect(nextWaiting(queue, "b")).toBe("c");
    expect(nextWaiting(queue, "c")).toBe("a");
  });

  it("vybraný, který už nečeká, začne znovu od nejstaršího", () => {
    expect(nextWaiting(queue, "zmizel")).toBe("a");
  });
});
