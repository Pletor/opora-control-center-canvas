import { describe, expect, it } from "vitest";
import type { Design } from "@/project/site-admin/logic/site-document";
import { MAX_HITS, searchDesign } from "./search";

const design = {
  readme: "", sections: [], cover: null,
  tokens: {
    color: { themes: [{ id: "light", name: "Light" }], tokens: [{ name: "ember", value: "rgb(214 88 42)", usage: "Primární akce" }, { name: "ink", value: { light: "#2a1f1a" } }] },
    type: { fonts: [], families: {}, groups: [{ name: "Text", styles: [{ name: "display", fontSize: "32px", sample: "Dobré ráno" }] }] },
    spacing: { tokens: [{ name: "space-1", value: "4px" }] },
  },
  components: [{ name: "Button", group: "Actions", summary: "Primární tlačítko", readme: "", preview: "", height: 200 }],
  assetGroups: [{ name: "Logos", readme: "", files: [{ name: "ember-mark.svg", blob: "assets/Logos/ember-mark.svg", size: 1, type: "image/svg+xml" }] }],
} as Design;

describe("hledání v design systému", () => {
  it("najde tokeny, styly, komponenty a assety a řekne, kam přepnout", () => {
    expect(searchDesign(design, "ember").map((hit) => [hit.section, hit.target])).toEqual([
      ["colors", "color-token-ember"], ["assets", "ds-asset-Logos-ember-mark.svg"]]);
    expect(searchDesign(design, "PRIMÁRNÍ").map((hit) => hit.target)).toEqual(["color-token-ember", "ds-component-Button"]);
    expect(searchDesign(design, "#2a1f")[0].label).toBe("ink");  // hodnota tématu
    expect(searchDesign(design, "ráno")[0]).toMatchObject({ section: "typography", target: "type-style-display", detail: "Text · 32px" });
    expect(searchDesign(design, "space")[0]).toMatchObject({ section: "spacing", target: "scale-spacing-space-1" });
    expect(searchDesign(design, "logos")[0]).toMatchObject({ section: "assets", target: "ds-asset-group-Logos" });
    expect(searchDesign(design, "  ")).toEqual([]);
  });

  it("výsledků je nejvýš MAX_HITS", () => {
    const many = { ...design, components: Array.from({ length: 50 }, (_x, index) => ({ name: "C" + index, readme: "", preview: "", height: 120 })) };
    expect(searchDesign(many, "c")).toHaveLength(MAX_HITS);
  });
});
