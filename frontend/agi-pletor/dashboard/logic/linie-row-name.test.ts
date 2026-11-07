import { describe, expect, it } from "vitest";
import { splitRowName } from "./linie-row-name";

describe("jméno řádku", () => {
  it("poslední segment tučně, prefix ztlumený", () => {
    expect(splitRowName("feat/velin-linie-strom")).toEqual({ prefix: "feat/velin-linie-", last: "strom" });
    expect(splitRowName("topic/knihovna")).toEqual({ prefix: "topic/", last: "knihovna" });
  });
  it("bez oddělovače, s mezerou nebo s oddělovačem na konci zůstane celé", () => {
    expect(splitRowName("main")).toEqual({ prefix: "", last: "main" });
    expect(splitRowName("Panel detailu-karty")).toEqual({ prefix: "", last: "Panel detailu-karty" });
    expect(splitRowName("feat/")).toEqual({ prefix: "", last: "feat/" });
  });
});
