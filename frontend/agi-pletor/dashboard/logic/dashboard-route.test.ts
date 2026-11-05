import { describe, expect, it } from "vitest";
import { isDashboardRoute, parsePart, withPart } from "./dashboard-route";

describe("dashboard-route", () => {
  it("čte část z adresy", () => expect(parsePart("?screen=pletor&part=hlas")).toBe("hlas"));
  it("bez části je Přehled", () => expect(parsePart("?screen=pletor")).toBe("prehled"));
  it("neznámá část je Přehled", () => expect(parsePart("?screen=pletor&part=nic")).toBe("prehled"));
  it("pozná stránku velínu", () => {
    expect(isDashboardRoute("?screen=pletor")).toBe(true);
    expect(isDashboardRoute("?screen=home")).toBe(false);
  });
  it("zapíše část a zachová projekt", () => {
    const url = withPart("?project=a&screen=home", "dilna");
    expect(url).toContain("project=a");
    expect(url).toContain("screen=pletor");
    expect(url).toContain("part=dilna");
  });
});
