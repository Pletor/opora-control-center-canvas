import { describe, expect, it } from "vitest";
import { briefUrl } from "./library-brief";

describe("briefUrl", () => {
  it("asks for the active version without a number and for a given version with it", () => {
    expect(briefUrl("f 1")).toBe("/api/library/flows/f%201/brief");
    expect(briefUrl("f", null)).toBe("/api/library/flows/f/brief");
    expect(briefUrl("f", 3)).toBe("/api/library/flows/f/brief?version=3");
  });
});
