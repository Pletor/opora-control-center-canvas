import { describe, expect, it } from "vitest";
import { changeWhen, orderBadge } from "./face-change";

describe("odznak pořadí", () => {
  it("fáze · pozice", () => {
    expect(orderBadge(302)).toBe("3·02");
    expect(orderBadge(1205)).toBe("12·05");
    expect(orderBadge(7)).toBe("0·07");
  });
  it("bez pořadí nic", () => {
    expect(orderBadge(null)).toBeNull();
    expect(orderBadge(undefined)).toBeNull();
    expect(orderBadge(-1)).toBeNull();
    expect(orderBadge(1.5)).toBeNull();
  });
});

describe("kdy", () => {
  it("kdy: dnes čas, včera, letos bez roku, jinak datum", () => {
    const now = new Date(2026, 9, 31, 12, 0);
    expect(changeWhen(new Date(2026, 9, 31, 11, 51).toISOString(), now)).toBe("11:51");
    expect(changeWhen(new Date(2026, 9, 30, 23, 0).toISOString(), now)).toBe("včera");
    expect(changeWhen(new Date(2026, 9, 6, 9, 0).toISOString(), now)).toBe("6. 10.");
    expect(changeWhen(new Date(2025, 11, 24, 9, 0).toISOString(), now)).toBe("24. 12. 2025");
    expect(changeWhen("x", now)).toBe("");
  });
});
