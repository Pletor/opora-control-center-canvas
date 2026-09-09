import type { Graph } from "./types";
export function projectMapModel(graph: Graph, projectName: string) {
  const byId = new Map(graph.nodes.map((n) => [n.id, n]));
  const depths = new Map<string, number>();
  for (const node of graph.nodes) {
    const chain: string[] = [];
    const seen = new Set<string>();
    let cursor: string | null = node.id;
    while (cursor !== null && !depths.has(cursor)) {
      if (seen.has(cursor) || !byId.has(cursor))
        throw new Error("Neplatná struktura projektu.");
      seen.add(cursor);
      chain.push(cursor);
      cursor = byId.get(cursor)!.parentId;
    }
    let depth = cursor === null ? 0 : depths.get(cursor)!;
    for (const id of chain.reverse()) depths.set(id, ++depth);
  }
  const children = new Map<string | null, string[]>();
  for (const node of graph.nodes)
    children.set(node.parentId, [
      ...(children.get(node.parentId) ?? []),
      node.id,
    ]);
  const vertical = new Map<string, number>();
  const stack = (children.get(null) ?? [])
    .slice()
    .reverse()
    .map((id) => ({ id, visited: false }));
  let leaf = 0;
  while (stack.length) {
    const item = stack.pop()!;
    const descendants = children.get(item.id) ?? [];
    if (!item.visited && descendants.length) {
      stack.push({ id: item.id, visited: true });
      for (const id of descendants.slice().reverse())
        stack.push({ id, visited: false });
    } else {
      vertical.set(
        item.id,
        descendants.length
          ? (vertical.get(descendants[0])! +
              vertical.get(descendants[descendants.length - 1])!) /
              2
          : leaf++ * 180,
      );
    }
  }
  const nodes = [
    {
      id: "project",
      entityId: null as string | null,
      label: projectName,
      kind: "project",
      x: 0,
      y: Math.max(0, leaf - 1) * 90,
    },
  ];
  for (const node of graph.nodes) {
    nodes.push({
      id: "node_" + node.id,
      entityId: node.id,
      label: node.name,
      kind: node.kind,
      x: depths.get(node.id)! * 400,
      y: vertical.get(node.id)!,
    });
  }
  const edges = [
    ...graph.nodes.map((n) => ({
      id: "contains_" + n.id,
      source: n.parentId === null ? "project" : "node_" + n.parentId,
      target: "node_" + n.id,
      kind: "contains",
      entityId: null as string | null,
    })),
    ...graph.edges.map((e) => ({
      id: "edge_" + e.id,
      source: "node_" + e.source,
      target: "node_" + e.target,
      kind: "link",
      entityId: e.id,
    })),
  ];
  return { nodes, edges };
}
export function archifySpecification(graph: Graph, name: string) {
  const model = projectMapModel(graph, name);
  return {
    schema_version: 1,
    diagram_type: "architecture",
    meta: { title: name + " — mapa projektu", quality_profile: "standard" },
    components: model.nodes.map((n) => ({
      id: n.id,
      type: n.kind === "project" ? "external" : "backend",
      label: n.label,
      sublabel:
        n.kind === "project"
          ? "Projekt"
          : n.kind === "sector"
            ? "Sektor"
            : "Uzel",
      pos: [n.x + 40, n.y + 40],
      size: [250, 90],
    })),
    connections: model.edges.map((e) => ({
      id: e.id,
      from: e.source,
      to: e.target,
      label: e.kind === "contains" ? "obsahuje" : "propojení",
      variant: e.kind === "contains" ? "dashed" : "default",
    })),
  };
}
export function downloadArchify(graph: Graph, name: string) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(archifySpecification(graph, name), null, 2)], {
      type: "application/json",
    }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = "opora-project-map.architecture.json";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
