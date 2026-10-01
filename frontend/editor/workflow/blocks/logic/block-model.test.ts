import { describe, expect, it } from "vitest";
import { addAction, addMaterial, addRule, blockNodeId, buildBlockNodes, captionMaterial, closeOpen, isBlockId, materialKindOf, materialPreviewUrl, moveAction, moveMaterial, parseBlockId, removeMaterial, removeRule, toggleOpen } from "./block-model";
import { emptyDesktopState } from "@/shared/desktop-state/logic/types";
import type { Graph } from "@/shared/types/logic/types";

const graph: Graph = {
  nodes: [{ id: "login", parentId: null, kind: "node", name: "Přihlášení", purpose: "", x: 100, y: 50 }],
  edges: [],
};
const api = { current: { mutate: async () => true, close: () => {}, pickPipeline: () => {}, uploadMaterial: async () => null, discardUpload: () => {}, previewUrl: () => null } };

describe("block-model", () => {
  it("přidá akci s ID, přesune ji a starý uzel bez bloků přitom doplní", () => {
    let state = addAction("login", { id: "verify.run-tests", label: "Testy", description: "" })(emptyDesktopState());
    state = addAction("login", { id: "handoff.report", label: "Zpráva", description: "" })(state);
    state = moveAction("login", 1, -1)(state);
    const actions = state.nodes.login.actions!;
    expect(actions.map((a) => a.pipelineId)).toEqual(["handoff.report", "verify.run-tests"]);
    expect(actions.every((a) => a.id.length > 0)).toBe(true);
    expect(state.nodes.login.rules).toEqual([]);
    expect(moveAction("login", 0, -1)(state).nodes.login.actions).toEqual(actions);
  });

  it("přidá a odebere pravidlo uzlu", () => {
    let state = addRule("login", "Heslo se neloguje.", "must_not")(emptyDesktopState());
    const id = state.nodes.login.rules![0].id;
    expect(state.nodes.login.rules![0].kind).toBe("must_not");
    state = removeRule("login", id)(state);
    expect(state.nodes.login.rules).toEqual([]);
  });

  it("blok je na plátně jen když je otevřený nebo má položky", () => {
    const empty = buildBlockNodes(graph, null, emptyDesktopState(), {}, false, api);
    expect(empty.nodes).toEqual([]);
    const opened = buildBlockNodes(graph, null, emptyDesktopState(), toggleOpen({}, "login", "rule"), false, api);
    expect(opened.nodes.map((n) => n.id)).toEqual(["block:rule:login"]);
    expect(opened.edges[0]).toMatchObject({ source: "login", sourceHandle: "rule", target: "block:rule:login" });
    expect(opened.nodes[0].position).toEqual({ x: 427, y: 239 });
    const withItems = buildBlockNodes(graph, null, addAction("login", { id: "p", label: "x", description: "" })(emptyDesktopState()), {}, false, api);
    expect(withItems.nodes.map((n) => n.data.port)).toEqual(["action"]);
    expect(isBlockId(withItems.nodes[0].id)).toBe(true);
  });

  it("přidá, popíše, přesune a odebere podklad uzlu", () => {
    let state = addMaterial("login", "upload", "a".repeat(32) + ".png", "návrh")(emptyDesktopState());
    state = addMaterial("login", "link", "https://example.com/spec", "")(state);
    const [first, second] = state.nodes.login.materials!;
    expect(first.kind).toBe("upload");
    state = captionMaterial("login", second.id, "spec")(state);
    state = moveMaterial("login", 1, -1)(state);
    expect(state.nodes.login.materials!.map((m) => m.caption)).toEqual(["spec", "návrh"]);
    state = removeMaterial("login", first.id)(state);
    expect(state.nodes.login.materials!.map((m) => m.id)).toEqual([second.id]);
    expect(materialKindOf("https://x.y/z")).toBe("link");
    expect(materialKindOf("docs/a.png")).toBe("source");
  });

  it("náhled podkladu vede na nahraný soubor nebo obrázek ve zdroji; odkaz náhled nemá", () => {
    const upload = { id: "m", kind: "upload" as const, path: "b".repeat(32) + ".png", caption: "" };
    expect(materialPreviewUrl("p", "w", "login", upload)).toBe(`/api/node-materials/file?project=p&nodeId=login&file=${upload.path}`);
    expect(materialPreviewUrl("p", "w", "login", { ...upload, kind: "source", path: "docs/a.png" })).toContain("/api/workspace/image?");
    expect(materialPreviewUrl("p", "w", "login", { ...upload, kind: "source", path: "docs/a.md" })).toBeNull();
    expect(materialPreviewUrl("p", "w", "login", { ...upload, kind: "link", path: "https://x" })).toBeNull();
  });

  it("blok podkladů stojí na místě pravidel, dokud pravidla nejsou vidět", () => {
    const alone = buildBlockNodes(graph, null, emptyDesktopState(), toggleOpen({}, "login", "material"), false, api);
    expect(alone.nodes.map((n) => n.id)).toEqual(["block:material:login"]);
    expect(alone.nodes[0].position).toEqual({ x: 427, y: 239 });
    const both = buildBlockNodes(graph, null, emptyDesktopState(), toggleOpen(toggleOpen({}, "login", "rule"), "login", "material"), false, api);
    expect(both.nodes.map((n) => n.position.y)).toEqual([239, 449]);
    expect(both.edges[1]).toMatchObject({ sourceHandle: "material", target: "block:material:login" });
  });

  it("odtažený blok stojí na uloženém posunu proti kartě a dá se táhnout dál", () => {
    const moved: Graph = {
      nodes: [{ ...graph.nodes[0], blockOffsets: { rule: { dx: -180, dy: 320 } } }],
      edges: [],
    };
    const open = toggleOpen({}, "login", "rule");
    // Bez posunu blok vyjde z výchozího místa (karta 100/50 + 327/189), s posunem z uloženého.
    expect(buildBlockNodes(graph, null, emptyDesktopState(), open, false, api).nodes[0].position).toEqual({ x: 427, y: 239 });
    expect(buildBlockNodes(moved, null, emptyDesktopState(), open, false, api).nodes[0].position).toEqual({ x: -80, y: 370 });
    // Posun platí jen pro svůj port: podklady dál stojí na svém výchozím místě u karty.
    const both = buildBlockNodes(moved, null, emptyDesktopState(), toggleOpen(open, "login", "material"), false, api);
    expect(both.nodes.map((n) => n.position)).toEqual([{ x: -80, y: 370 }, { x: 427, y: 449 }]);
    expect(both.nodes.every((n) => n.draggable === true && n.selectable === false)).toBe(true);
    // Jen ke čtení: blok je na svém místě, ale odtáhnout ho nejde (vlastní `draggable` přebíjí plátno).
    expect(buildBlockNodes(moved, null, emptyDesktopState(), open, true, api).nodes[0].draggable).toBe(false);
  });

  it("id bloku se rozebere zpátky na uzel a port; cizí id vrátí null", () => {
    expect(parseBlockId(blockNodeId("login", "material"))).toEqual({ nodeId: "login", port: "material" });
    expect(parseBlockId("login")).toBeNull();
    expect(parseBlockId("block:unknown:login")).toBeNull();
    expect(parseBlockId("block:rule:")).toBeNull();
  });

  it("otevření a zavření portu je idempotentní", () => {
    const open = toggleOpen(toggleOpen({}, "login", "action"), "login", "action");
    expect(open.login).toEqual([]);
    expect(closeOpen(toggleOpen({}, "login", "rule"), "login", "rule").login).toEqual([]);
  });
});
