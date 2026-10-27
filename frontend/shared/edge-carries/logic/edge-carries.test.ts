import { describe, expect, it } from "vitest";
import { canCarry, carriesLook, CARRIES_LABEL, parseCarries } from "./edge-carries";

describe("edge-carries", () => {
  it("smí ho nést jen vazba next nebo bez portu", () => {
    expect(canCarry({})).toBe(true);
    expect(canCarry({ port: "next" })).toBe(true);
    for (const port of ["flow", "rule", "action", "block"] as const) expect(canCarry({ port })).toBe(false);
  });

  it("výběr: prázdno a neznámá hodnota jsou neurčeno", () => {
    expect(parseCarries("data")).toBe("data");
    expect(parseCarries("")).toBeNull();
    expect(parseCarries("flow")).toBeNull();
  });

  it("každý druh má třídu-háček, barvu z tokenu, tooltip a vlastní čáru; bez carries nic", () => {
    expect(carriesLook(undefined)).toBeNull();
    expect(carriesLook("navigation")).toEqual({ className: "edge--carries-navigation", stroke: "var(--edge-carries-navigation)",
      extraWidth: 0, title: "Po vazbě teče: Navigace" });
    expect(carriesLook("data")).toMatchObject({ stroke: "var(--edge-carries-data)", extraWidth: 0 });
    expect(carriesLook("data")!.dash).toBeUndefined();
    expect(carriesLook("command")).toMatchObject({ extraWidth: 0.5 });
    expect(carriesLook("event")).toMatchObject({ dash: "6 4", extraWidth: 0 });
    expect(Object.keys(CARRIES_LABEL)).toEqual(["navigation", "data", "command", "event"]);
  });
});
