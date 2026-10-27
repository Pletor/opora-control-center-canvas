// Převedeno z prototypu `test/model.test.mjs`, `connection-policy.test.mjs`, `connection-menu.test.mjs`,
// `technology.test.mjs` (jen vazby) a `architecture-areas.test.mjs` (nabídka bez samostatného Podu).
import { describe, expect, it } from "vitest";
import { catalog } from "./catalog";
import { connectionChoices } from "./connection-choices";
import { TYPED_POLICY } from "./connection-policy";
import { connect, connectionError, createNode, MAX_NODES, removeNode, validateModel } from "./model-rules";
import { emptyStudioModel, type StudioModel } from "./model-types";

const model = (...types: string[]): StudioModel => {
  const m = emptyStudioModel("domain");
  types.forEach((type, i) => m.nodes.push(createNode(type, { x: i * 300, y: 0 }, `n${i}`)));
  return m;
};
const ref = (nodeId: string, portId: string) => ({ nodeId, portId });

describe("connectionError", () => {
  it("všech 68 typů: kartézská kontrola typů vstupních a výstupních portů", () => {
    let checks = 0;
    for (const a of catalog) for (const b of catalog) {
      const m = model(a.id, b.id);
      for (const out of a.ports.filter((p) => p.direction === "output"))
        for (const input of b.ports.filter((p) => p.direction === "input")) {
          expect(connectionError(m, ref("n0", out.id), ref("n1", input.id), undefined, TYPED_POLICY) === null, `${a.name}.${out.id} → ${b.name}.${input.id}`).toBe(out.type === input.type);
          checks++;
        }
    }
    expect(checks).toBeGreaterThan(1000);
  });

  it("Client → Frontend → Service → PostgreSQL bez rolí; směr, typ a existence se kontrolují", () => {
    let m = model("client", "frontend-app", "service", "postgresql");
    for (const [a, out, b, input] of [["n0", "http-out", "n1", "http-in"], ["n1", "http-out", "n2", "http-in"], ["n2", "sql-out", "n3", "sql-in"]])
      m = connect(m, ref(a, out), ref(b, input), TYPED_POLICY).model;
    expect(m.edges.map((e) => e.type)).toEqual(["http-request", "http-request", "sql-query"]);
    expect(() => connect(m, ref("n0", "http-out"), ref("n3", "sql-in"), TYPED_POLICY)).toThrow(/Nekompatibilní/);
    expect(connectionError(m, ref("n1", "http-in"), ref("n0", "http-out"))).toMatch(/výstupu na vstup/);
    expect(connectionError(m, ref("n0", "http-out"), ref("n1", "http-in"), undefined, TYPED_POLICY)).toMatch(/již existuje/);
    expect(connectionError(m, ref("x", "http-out"), ref("n1", "http-in"))).toMatch(/neexistuje/);
    expect(connectionError(m, null, ref("n1", "http-in"))).toMatch(/Chybí/);
    const removed = removeNode(m, "n1");
    expect(removed.edges).toHaveLength(1);
    expect(m.edges).toHaveLength(3);
  });

  it("role Studia: Client nesmí přímo na Service, AI jen přes bránu", () => {
    const m = model("client", "service", "api-gateway", "ai-inference");
    expect(() => connect(m, ref("n0", "http-out"), ref("n1", "http-in"))).toThrow(/Role Studia/);
    expect(connectionError(m, ref("n0", "http-out"), ref("n3", "http-in"))).toMatch(/Role/);
    expect(connectionError(m, ref("n2", "http-out"), ref("n3", "http-in"))).toBeNull();
  });

  it("dva jističe se propojí, jistič sám se sebou ne; mimo HTTP platí typy", () => {
    let m = model("circuit-breaker", "circuit-breaker", "service", "postgresql");
    m = connect(m, ref("n0", "http-out"), ref("n1", "http-in")).model;
    expect(connectionError(m, ref("n0", "http-out"), ref("n0", "http-in"))).toMatch(/samu/);
    m = connect(m, ref("n2", "sql-out"), ref("n3", "sql-in")).model;
    expect(connectionError(m, ref("n0", "http-out"), ref("n3", "sql-in"))).toMatch(/Nekompatibilní/);
  });
});

describe("validateModel", () => {
  it("platný model projde a neplatný se odmítne s důvodem", () => {
    const { model: m } = connect(model("api-gateway", "service"), ref("n0", "http-out"), ref("n1", "http-in"));
    expect(validateModel(m)).toBe(m);
    expect(() => validateModel({ ...m, schema: "x" as never })).toThrow(/verze/);
    expect(() => validateModel({ ...m, nodes: [m.nodes[0], { ...m.nodes[1], id: "n0" }] })).toThrow(/duplicitní/);
    expect(() => validateModel({ ...m, nodes: [m.nodes[0]] })).toThrow(/neexistuje/);
    expect(() => validateModel({ ...m, nodes: [{ ...m.nodes[0], type: "neznamy" }, m.nodes[1]] })).toThrow(/komponenta/);
    expect(() => validateModel({ ...m, edges: [{ ...m.edges[0], type: "event" }] })).toThrow(/typ/);
    expect(() => validateModel({ ...m, nodes: [{ ...m.nodes[0], binding: { nodeId: "" } }, m.nodes[1]] })).toThrow(/OPORY/);
    expect(() => validateModel({ ...m, revision: -1 })).toThrow(/revize/);
    const many = emptyStudioModel("d");
    for (let i = 0; i <= MAX_NODES; i++) many.nodes.push(createNode("service", undefined, "s" + i));
    expect(() => validateModel(many)).toThrow(/limit/);
  });
});

describe("connectionChoices", () => {
  it("nabídka používá role, typy i duplicity a model nemění", () => {
    let m = model("client", "frontend-app", "postgresql");
    const before = structuredClone(m), choices = connectionChoices(m, ref("n0", "http-out"));
    expect(m).toEqual(before);
    expect(choices.existing.some((c) => c.nodeId === "n1")).toBe(true);
    expect(choices.existing.some((c) => c.nodeId === "n2")).toBe(false);
    expect(choices.create.some((c) => c.type === "frontend-app")).toBe(true);
    expect(choices.create.some((c) => c.type === "postgresql")).toBe(false);
    expect(connectionChoices(m, ref("n0", "http-out"), "not a component").create).toHaveLength(0);
    expect(connectionChoices(m, ref("n0", "http-out"), "Frontend").existing.every((c) => c.nodeId === "n1")).toBe(true);
    m = connect(m, ref("n0", "http-out"), ref("n1", "http-in")).model;
    expect(connectionChoices(m, ref("n0", "http-out")).existing.some((c) => c.nodeId === "n1")).toBe(false);
  });

  it("samostatný Pod se nenabízí k vytvoření, existující Pod ano", () => {
    const m = model("load-balancer", "pod"), choices = connectionChoices(m, ref("n0", "http-out"), "", TYPED_POLICY);
    expect(choices.create.some((c) => c.type === "pod")).toBe(false);
    expect(choices.existing.some((c) => c.nodeId === "n1")).toBe(true);
  });
});
