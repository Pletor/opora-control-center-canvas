import { describe, expect, it } from "vitest";
import { CONTRACT } from "./contract";

describe("data-oh contract table", () => {
  it("names only data-oh-* attributes or the JSON mirror", () => {
    for (const row of CONTRACT) {
      const names = row.attribute.split(" · ").map(item => item.split("=")[0].trim());
      expect(names.every(name => name.startsWith("data-oh-") || name.startsWith("script#oh-"))).toBe(true);
    }
  });
  it("covers the attributes the design requires", () => {
    const all = CONTRACT.map(row => row.attribute).join(" ");
    for (const name of ["data-oh-stage", "data-oh-health", "data-oh-action-id", "data-oh-action-status", "data-oh-accepted-head", "data-oh-execution", "data-oh-epoch"])
      expect(all).toContain(name);
  });
  it("never exposes the identity nonce through data-oh or a mirror", () => {
    expect(CONTRACT.map(row => `${row.attribute} ${row.jsonPath}`).join(" ")).not.toMatch(/nonce|data-oh-marker/);
  });
});
