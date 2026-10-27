// Převedeno z prototypu `test/geometry.test.mjs` a `test/architecture-areas.test.mjs` (bez simulace a bez REA
// důkazních souborů; hodnoty rozměrů Deploymentu jsou ty, které prototyp ověřil proti záznamům běhu).
import { describe, expect, it } from "vitest";
import { catalog } from "./catalog";
import { architectureAreas, cardGeometry, controllerGeometry, observedPortPosition, withManualPodView, type ControllerState } from "./geometry";
import { createNode } from "./model-rules";
import { observedGeometry } from "./observed-geometry";

describe("geometrie karet", () => {
  it("běžné typy mají změřený rozměr, Skutečnost jednotnou kartu", () => {
    for (const type of catalog.filter((c) => c.id !== "kubernetes-deployment"))
      expect(cardGeometry({ type: type.id }), type.id).toEqual({ width: observedGeometry[type.id].width, height: observedGeometry[type.id].height });
    expect(cardGeometry({ type: "service" }, { model: false })).toEqual({ width: 270, height: 230 });
    expect(() => cardGeometry({ type: "neznamy" })).toThrow(/geometry/);
  });

  it("každý ze 227 portů leží na své straně obvodu při libovolném rozměru", () => {
    let checked = 0;
    for (const type of catalog) for (const port of type.ports) {
      const anchor = observedGeometry[type.id].ports.find((p) => p.id === port.id)!, p = observedPortPosition(type.id, port.id, { width: 280, height: 195 });
      expect(p.side).toBe(anchor.side);
      expect(p.x).toBe(anchor.side === "left" ? 0 : anchor.side === "right" ? 280 : 280 * anchor.fraction);
      expect(p.y).toBe(anchor.side === "top" ? 0 : anchor.side === "bottom" ? 195 : 195 * anchor.fraction);
      checked++;
    }
    expect(checked).toBe(227);
  });

  it("Deployment se dvěma a třemi Pody má změřený rozměr; ručně přidaný Pod kartu prodlouží", () => {
    expect(controllerGeometry(2)).toMatchObject({ width: 518, height: 309, podWidth: 220, podHeight: 158 });
    expect(controllerGeometry(3).height).toBe(483);
    let state: ControllerState = { instances: [{ id: "p1" }, { id: "p2" }] };
    for (const id of ["p3", "p4", "p5"]) {
      const previous = state, before = structuredClone(previous);
      state = withManualPodView({ instances: [...previous.instances.map((p) => ({ ...p })), { id }] }, previous);
      expect(previous).toEqual(before);
    }
    expect(state.instances[4].viewOffset).toEqual({ profile: "studio-observed/1", x: 20, y: 483 });
    expect(controllerGeometry(5, state.instances).height).toBe(661);
    expect(controllerGeometry(3, state.instances.slice(0, 3)).height).toBe(485);
  });
});

describe("architectureAreas", () => {
  it("prázdný model a Skutečnost podklad nemají", () => {
    expect(architectureAreas({ nodes: [] })).toEqual([]);
    expect(architectureAreas({ nodes: [createNode("service", undefined, "s")] }, { model: false })).toEqual([]);
    expect(architectureAreas({ nodes: [createNode("service", undefined, "s")] })).toHaveLength(1);
  });

  it("posun karty přepočítá obálku rodiny včetně záporných poloh a nic nemění", () => {
    const a = createNode("client", { x: 80, y: 150 }, "a"), b = createNode("frontend-app", { x: 340, y: 120 }, "b");
    const first = architectureAreas({ nodes: [a, b] })[0];
    expect(first.members).toEqual(["a", "b"]);
    const moved = architectureAreas({ nodes: [a, { ...b, position: { x: 440, y: 80 } }] })[0];
    expect(moved.left).toBe(first.left);
    expect(moved.top).toBe(first.top - 40);
    expect(moved.width).toBe(first.width + 100);
    expect(moved.height).toBe(first.height + 40);
    expect(b.position).toEqual({ x: 340, y: 120 });
  });

  it("Pody Deploymentu patří do rodiny výpočtu, Deployment do bran", () => {
    const parent = createNode("kubernetes-deployment", { x: 100, y: 200 }, "k");
    const controllers = { k: { instances: [{ id: "p1" }, { id: "p2" }] } }, before = structuredClone(controllers);
    const areas = architectureAreas({ nodes: [parent] }, { controllers });
    expect(areas.find((a) => a.id === "gateway-routing")!.members).toEqual(["k"]);
    expect(areas.find((a) => a.id === "compute")!.members).toEqual(["p1", "p2"]);
    expect(controllers).toEqual(before);
  });
});
