import { describe, expect, it } from "vitest";
import { ApiError } from "@/shared/types/logic/types";
import { cardCycleError } from "./card-cycle";

describe("cyklus karet z 409", () => {
  it("vypíše cestu jmény karet", () => {
    const error = new ApiError("cycle", 409, { error: "cycle", code: "card_cycle", cycle: ["b", "a", "b"] });
    expect(cardCycleError(error, (id) => ({ a: "Alfa", b: "Beta" })[id])?.message)
      .toBe("Vazba „další krok“ by uzavřela cyklus karet: Beta → Alfa → Beta. Graf závislostí musí zůstat bez cyklů, nic se neuložilo.");
  });
  it("jiné chyby nechá být", () => {
    expect(cardCycleError(new ApiError("x", 409, { code: "stale" }), () => "")).toBeNull();
    expect(cardCycleError(new Error("x"), () => "")).toBeNull();
  });
});
