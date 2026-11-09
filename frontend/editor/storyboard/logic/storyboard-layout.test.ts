import { describe, expect, it } from "vitest";
import { kulicka } from "./animations/kulicka";
import { ANNOTATION_LAYER, storyboardScope, cardsForPicker, defaultVisible, layersOf, paintLayers, toggleLayer } from "./storyboard-layout";

describe("rozvržení storyboardu", () => {
  it("do výběru jdou jen karty, abecedně", () => {
    const graph = { nodes: [
      { id: "s", kind: "sector", name: "Sektor" }, { id: "b", kind: "node", name: "Ždímačka" },
      { id: "c", kind: "comment", name: "Pozn." }, { id: "a", kind: "node", name: "Auto" }, { id: "e", kind: "node", name: "" },
    ] };
    expect(cardsForPicker(graph)).toEqual([{ id: "a", name: "Auto" }, { id: "e", name: "e" }, { id: "b", name: "Ždímačka" }]);
    expect(cardsForPicker({ nodes: [] })).toEqual([]);
  });
  it("vrstvy animace pokračují skicou a končí vrstvou šipek a poznámek", () => {
    const layers = layersOf(kulicka);
    expect(layers.map((l) => l.id)).toEqual(["pozadi", "stin", "kulicka", "skica", ANNOTATION_LAYER]);
    expect(layers.at(-1)?.label).toBe("Šipky a poznámky");
  });
  it("výchozí je vidět vše", () => {
    expect([...defaultVisible(kulicka)]).toEqual(["pozadi", "stin", "kulicka", "skica", ANNOTATION_LAYER]);
  });
  it("toggleLayer schová a znovu ukáže, původní množinu nemění", () => {
    const all = defaultVisible(kulicka);
    const hidden = toggleLayer(all, "stin");
    expect(hidden.has("stin")).toBe(false);
    expect(all.has("stin")).toBe(true);
    expect(toggleLayer(hidden, "stin").has("stin")).toBe(true);
  });
  it("paintLayers vynechá vrstvu anotací", () => {
    expect(paintLayers(defaultVisible(kulicka)).has(ANNOTATION_LAYER)).toBe(false);
    expect(paintLayers(defaultVisible(kulicka)).has("kulicka")).toBe(true);
  });
});

it("keeps the entered scope independently of a selected child and preserves root overview", () => {
  const nodes = [{ id: "login", kind: "node" }, { id: "tenant", kind: "node" }, { id: "area", kind: "sector" }];
  expect(storyboardScope(nodes, "login")).toBe(nodes[0]);
  expect(storyboardScope(nodes, "tenant")).toBe(nodes[1]);
  expect(storyboardScope(nodes, "area")).toBe(nodes[2]);
  expect(storyboardScope(nodes, null)).toBeNull();
});
