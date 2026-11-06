import { describe, expect, it } from "vitest";
import { depthOf, parentOf } from "./linie-tree";

const heads = ["main", "develop", "feat/velin", "feat/velin-linie", "feat/velin-linie-strom", "items/tlacitko"];

describe("parentOf", () => {
  it("pevné větve", () => {
    expect(parentOf("develop", heads)).toBe("main");
    expect(parentOf("items/tlacitko", heads)).toBe("develop");
    expect(parentOf("hotfix/x", heads)).toBe("main");
    expect(parentOf("main", heads)).toBeNull();
  });
  it("feat bere nejdelší existující prefix na hranici -", () => {
    expect(parentOf("feat/velin", heads)).toBe("develop");
    expect(parentOf("feat/velin-linie", heads)).toBe("feat/velin");
    expect(parentOf("feat/velin-linie-strom", heads)).toBe("feat/velin-linie");
    expect(parentOf("feat/velin-linie-strom-nove", heads)).toBe("feat/velin-linie-strom");
  });
  it("feat/velinzzz není dítě feat/velin", () => {
    expect(parentOf("feat/velinzzz", heads)).toBe("develop");
  });
  it("chybějící mezičlánek přeskočí na nejbližší existující", () => {
    expect(parentOf("feat/velin-a-b", heads)).toBe("feat/velin");
    expect(parentOf("feat/nic-a-b", heads)).toBe("develop");
  });
  it("fix a experiment jsou neodvozeno", () => {
    expect(parentOf("fix/x", heads)).toBeNull();
    expect(parentOf("experiment/y", heads)).toBeNull();
  });
});

describe("depthOf", () => {
  it("hloubka po řetězu rodičů", () => {
    expect(depthOf("main", heads)).toBe(0);
    expect(depthOf("develop", heads)).toBe(1);
    expect(depthOf("feat/velin", heads)).toBe(2);
    expect(depthOf("feat/velin-linie-strom", heads)).toBe(4);
    expect(depthOf("fix/x", heads)).toBe(0);
  });
});
