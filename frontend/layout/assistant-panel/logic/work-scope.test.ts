import { describe, expect, it } from "vitest";
import { selectionLabel, SCOPE_LABEL } from "./work-scope";

describe("rozsah práce", () => {
  it("počet vybraných uzlů slovy", () => {
    expect(selectionLabel(0)).toBe("nic nevybráno");
    expect(selectionLabel(1)).toBe("Výběr: 1 uzel");
    expect(selectionLabel(2)).toBe("Výběr: 2 uzly");
    expect(selectionLabel(5)).toBe("Výběr: 5 uzlů");
  });

  it("jména módů", () => {
    expect(SCOPE_LABEL).toEqual({ selection: "Výběr", board: "Celý obraz" });
  });
});
