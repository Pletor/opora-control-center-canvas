import { describe, expect, it } from "vitest";
import { branchColor, hueOf } from "./linie-color";

const rows = [
  { branch: "main", type: "main", parent: "" },
  { branch: "develop", type: "develop", parent: "main" },
  { branch: "feat/velin", type: "work", parent: "develop" },
  { branch: "feat/velin-linie", type: "work", parent: "feat/velin" },
  { branch: "feat/velin-linie-strom", type: "work", parent: "feat/velin-linie" },
  { branch: "feat/canvas-2", type: "work", parent: "develop" },
  { branch: "feat/sirotek-x", type: "work", parent: "feat/sirotek" },
  { branch: "", name: "Plán bez větve", type: "work", parent: "develop" },
];

describe("branchColor", () => {
  it("pevné barvy podle větve i typu řádku", () => {
    expect(["main", "develop", "items/btn", "fix/popis", "experiment/v"].map((b) => branchColor(b, rows)))
      .toEqual(["#4ade80", "#60a5fa", "#c084fc", "#f87171", "#a39cc4"]);
    expect(branchColor("topic/knihovna", [{ branch: "topic/knihovna", type: "items", parent: "develop" }])).toBe("#c084fc");
  });
  it("každý kořen feat má vlastní stabilní odstín", () => {
    const velin = branchColor("feat/velin", rows), canvas = branchColor("feat/canvas-2", rows);
    expect(velin).toBe(`hsl(${hueOf("feat/velin")} 75% 56%)`);
    expect(canvas).toBe(`hsl(${hueOf("feat/canvas-2")} 75% 56%)`);
    expect(velin).not.toBe(canvas);
    expect(branchColor("feat/velin", rows)).toBe(velin);
  });
  it("dítě dědí odstín kořene, s hloubkou bledne a světlá, se stropem", () => {
    const hue = hueOf("feat/velin");
    expect(branchColor("feat/velin-linie", rows)).toBe(`hsl(${hue} 66% 64%)`);
    expect(branchColor("feat/velin-linie-strom", rows)).toBe(`hsl(${hue} 57% 72%)`);
    const deep = Array.from({ length: 8 }, (_, i) => ({ branch: `feat/a${"-x".repeat(i)}`, parent: i ? `feat/a${"-x".repeat(i - 1)}` : "develop" }));
    expect(branchColor(deep[7].branch, [...rows, ...deep])).toBe(`hsl(${hueOf("feat/a")} 45% 80%)`);
  });
  it("neznámý rodič = develop, větev bez řádku i řádek bez větve jsou kořenem", () => {
    expect(branchColor("feat/sirotek-x", rows)).toBe(`hsl(${hueOf("feat/sirotek-x")} 75% 56%)`);
    expect(branchColor("feat/nikde", [])).toBe(`hsl(${hueOf("feat/nikde")} 75% 56%)`);
    expect(branchColor("Plán bez větve", rows)).toBe(`hsl(${hueOf("Plán bez větve")} 75% 56%)`);
  });
  it("lane Git grafu (name + role) se barví stejně", () => {
    const lanes = [{ name: "develop", role: "develop", parent: "main" }, { name: "feat/velin", role: "feat", parent: "develop" }, { name: "feat/velin-linie", role: "feat", parent: "feat/velin" }];
    expect(branchColor("feat/velin-linie", lanes)).toBe(branchColor("feat/velin-linie", rows));
  });
});
