// Převedeno z prototypu `test/studio-routing.test.mjs`; poslední test bez simulace (S5) ověřuje jen neměnnost modelu.
import { describe, expect, it } from "vitest";
import { componentType } from "./catalog";
import { connect, createNode } from "./model-rules";
import { emptyStudioModel } from "./model-types";
import { observedGeometry } from "./observed-geometry";
import { layoutStudioConnections, type LayoutEdge, type LayoutNode } from "./studio-routing";

type Port = LayoutNode["ports"][number];
const box = (id: string, x: number, y: number, ports: Port[]): LayoutNode => ({ id, x, y, width: 220, height: 178, ports });
const source = () => box("s", 340, 120, [{ id: "data", direction: "input", side: "left" }, { id: "event", direction: "output", side: "right" }]);
const target = (x = 780, y = 120, id = "t") => box(id, x, y, Array.from({ length: 9 }, (_, i): Port => ({ id: i === 1 ? "event" : "p" + i, direction: "input", side: i === 1 ? "top" : "left" })));
const edge = (id = "e", to = "t"): LayoutEdge => ({ id, enabled: true, from: { nodeId: "s", portId: "event" }, to: { nodeId: to, portId: "event" } });
const sides = (r: ReturnType<typeof layoutStudioConnections>) => [r.ports.get("s")!.get("event")!.side, r.ports.get("t")!.get("event")!.side];

describe("layoutStudioConnections", () => {
  it("výchozí strany se otočí k protějšku ve všech čtyřech směrech", () => {
    const a = source(), b = target(), before = structuredClone([a, b]);
    expect(sides(layoutStudioConnections([a, b], []))).toEqual(["right", "top"]);
    for (const [x, y, expected] of [[780, 120, ["right", "left"]], [70, 120, ["left", "right"]], [340, 450, ["bottom", "top"]], [340, -200, ["top", "bottom"]]] as const) {
      const r = layoutStudioConnections([a, target(x, y)], [edge()]);
      expect(sides(r)).toEqual(expected);
      expect(r.ports.get("s")!.get("event")!.fraction).toBe(2 / 3);
      expect(r.ports.get("t")!.get("event")!.fraction).toBe(0.2);
      expect(r.routes.get("e")!.kind).toBe("bezier");
    }
    expect([a, b]).toEqual(before);
  });

  it("sdílený port míří ke středu protějšků a drží jednu kotvu", () => {
    const a = source(), left = target(76.6318, 270), right = target(780, 270, "u");
    a.y = 270;
    let r = layoutStudioConnections([a, left, right], [edge(), edge("f", "u")]);
    expect(r.ports.get("s")!.get("event")!.side).toBe("right");
    a.x = 476.6445;
    r = layoutStudioConnections([a, left, right], [edge(), edge("f", "u")]);
    expect(r.ports.get("s")!.get("event")!.side).toBe("left");
    expect(r.routes.get("e")!.start).toEqual(r.routes.get("f")!.start);
    expect(r.ports.get("t")!.get("event")!.side).toBe("right");
    expect(r.ports.get("u")!.get("event")!.side).toBe("left");
    expect(layoutStudioConnections([a, left, right], [edge(), edge("f", "u")])).toEqual(r);
  });

  it("vypnutá nebo smazaná vazba vrátí konce do výchozích stran", () => {
    const nodes = [source(), target(70, 120)], e = edge(), before = structuredClone({ nodes, e });
    expect(sides(layoutStudioConnections(nodes, [e]))).toEqual(["left", "right"]);
    const disabled = layoutStudioConnections(nodes, [{ ...e, enabled: false }]);
    expect(sides(disabled)).toEqual(["right", "top"]);
    expect(disabled.routes.get("e")!.inactive).toBe(true);
    expect(sides(layoutStudioConnections(nodes, []))).toEqual(["right", "top"]);
    expect({ nodes, e }).toEqual(before);
  });

  it("vzorkování smí vybrat jinou než první dvojici stran; objížďka není zaručená", () => {
    const nodes = [source(), target(), { id: "block", x: 670, y: 200, width: 20, height: 20, ports: [] }];
    const route = layoutStudioConnections(nodes, [edge()]).routes.get("e")!;
    expect(route.candidateIndex).toBeGreaterThan(0);
    expect(route.probeClear).toBe(true);
    expect(["top", "bottom"].includes(route.sourceSide!) || ["top", "bottom"].includes(route.targetSide!)).toBe(true);
    const wall = { id: "wall", x: -1000, y: -1000, width: 4000, height: 4000, ports: [] };
    const blocked = layoutStudioConnections([...nodes, wall], [edge()]).routes.get("e")!;
    expect(blocked.candidateIndex).toBe(0);
    expect(blocked.probeClear).toBe(false);
    expect(blocked.kind).toBe("bezier");
  });

  it("neúplné konce se bezpečně přeskočí a víc vstupů sdílí kotvu", () => {
    const a = source(), b = target(), other = { ...source(), id: "u", x: 400, y: 600 }, e = edge();
    const f: LayoutEdge = { id: "f", from: { nodeId: "u", portId: "event" }, to: { nodeId: "t", portId: "event" }, enabled: true };
    const r = layoutStudioConnections([a, b, other], [e, f, { id: "bad", from: { nodeId: "missing", portId: "x" }, to: e.to }]);
    expect(r.routes.size).toBe(2);
    expect(r.routes.get("e")!.end).toEqual(r.routes.get("f")!.end);
    expect(r.ports.get("t")!.get("event")!.fraction).toBe(0.2);
  });

  it("rozložení nad skutečným modelem model nemění", () => {
    let m = emptyStudioModel("d");
    m.nodes.push(createNode("aws-s3", { x: 0, y: 0 }, "s3"), createNode("aws-lambda", { x: 400, y: 0 }, "fn"));
    const out = componentType("aws-s3")!.ports.find((p) => p.type === "event" && p.direction === "output")!;
    const input = componentType("aws-lambda")!.ports.find((p) => p.type === "event" && p.direction === "input")!;
    m = connect(m, { nodeId: "s3", portId: out.id }, { nodeId: "fn", portId: input.id }).model;
    const before = structuredClone(m);
    const boxes = m.nodes.map((n): LayoutNode => ({ id: n.id, x: n.position.x, y: n.position.y, width: observedGeometry[n.type].width, height: observedGeometry[n.type].height,
      ports: componentType(n.type)!.ports.map((p) => ({ ...p, side: observedGeometry[n.type].ports.find((o) => o.id === p.id)!.side })) }));
    expect(layoutStudioConnections(boxes, m.edges).routes.size).toBe(1);
    expect(m).toEqual(before);
  });
});
