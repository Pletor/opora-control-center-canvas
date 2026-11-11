import { describe, expect, it } from "vitest";
import { chipFit } from "./chip-fit";

describe("štítky v boxu", () => {
  it("široký vysoký box pojme všechny štítky pod hlavičkou", () => {
    expect(chipFit(4, 1, 4, true)).toEqual({ shown: 4, head: false });
  });
  it("co se nevejde, nechá místo pro +N", () => {
    expect(chipFit(9, 6 / 12, 2, true)).toEqual({ shown: 1, head: false });
  });
  it("box s vnořenými boxy nebo nízký box nese štítky v hlavičce", () => {
    expect(chipFit(3, 1, 6, false)).toEqual({ shown: 3, head: true });
    expect(chipFit(5, 1, 1, true)).toEqual({ shown: 3, head: true });
    expect(chipFit(2, 3 / 12, 1, true)).toEqual({ shown: 0, head: true });
  });
});
