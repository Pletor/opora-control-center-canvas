import { describe, expect, it } from "vitest";
import { pendingSelection } from "./select-request";

describe("výběr úkolu zvenku panelu", () => {
  it("vybere úkol, až je v seznamu, a každou žádost jen jednou", () => {
    const request = { seq: 2, sessionId: "s2" };
    expect(pendingSelection(request, 0, [])).toBeNull();
    expect(pendingSelection(request, 0, ["s1", "s2"])).toBe("s2");
    expect(pendingSelection(request, 2, ["s1", "s2"])).toBeNull();
    expect(pendingSelection(null, 0, ["s2"])).toBeNull();
  });
});
