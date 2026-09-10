export type RemovalPreview = { project: string; workspace: string; kind: "node" | "edge" | "project"; target: string; label: string; nodeIds: string[]; nodeCount: number; edgeCount: number; workspaceCount?: number; digest: string };
export type SpecFields = { goal: string; non_goals: string; acceptance: string };
export type NodeSpec = { fields: SpecFields; revision: number; saved_at: string | null; readOnly: boolean; available: boolean; source: string };
export type CanvasNode = {
  id: string;
  parentId: string | null;
  kind: "sector" | "node";
  name: string;
  purpose: string;
  x: number;
  y: number;
};
export type Graph = {
  nodes: CanvasNode[];
  edges: { id: string; source: string; target: string }[];
};
export type Workspace = {
  id: string;
  directory: string;
  branch: string;
  node_id: string;
  actor: string;
  base_sha: string;
};
export type View = {
  graph: Graph;
  digest: string;
  readOnly: boolean;
  source: string;
  sha: string | null;
  branch: string | null;
  dirty: boolean;
  graphStatus: string;
  workspaces: Workspace[];
  observedAt: string;
};
export type Project = { id: string; name: string; url: string | null; branch: string | null; sourceKind?: string; sourcePath?: string | null };
export type Job = {
  id: string;
  kind: string;
  status: string;
  message: string;
  project_id: string;
  updated_at: string;
};
export async function api<T>(url: string, body?: object): Promise<T> {
  const response = await fetch(
    url,
    body
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : undefined,
  );
  // Chybějící endpoint (statický 404) nesmí vypadat jako JSON chyba parseru: říká se HTTP stav.
  const raw = await response.text();
  let value: { error?: string } & Record<string, unknown>;
  try {
    value = JSON.parse(raw);
  } catch {
    throw new Error(`${url.split("?")[0]} není dostupné (HTTP ${response.status}).`);
  }
  if (!response.ok) throw new Error(value.error ?? `Požadavek se nezdařil (HTTP ${response.status}).`);
  return value as T;
}
