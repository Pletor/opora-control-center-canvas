// Malý platný spec PR Lens pro testy: dvě čočky, pohled na každou, tok s payloadem (před/po) a průvodce.
const HEAD = "373909b753fc26e105264c5f6e35b02afb3e057d";

export const LENS_SPEC = {
  schemaVersion: "0.2.0", kind: "graph", title: "Pinned merge", summary: "The merge button sends the head it showed.",
  lenses: ["architecture", "data-flow"],
  provenance: { repo: { owner: "Pletor", name: "agent-office", host: "github.com" },
    base: { sha: "63c70f1c42394e0a00de74d580c95bfc5caf0f60", ref: "main" }, head: { sha: HEAD },
    pullRequest: { number: 44, title: "fix(cleanline): pin merge", url: "https://github.com/Pletor/agent-office/pull/44" } },
  lanes: [{ id: "client", label: "Browser", order: 0 }, { id: "server", label: "Office server", order: 1 }],
  nodes: [
    { id: "queue-tab", label: "Merge queue tab", kind: "ui", delta: "modified", lane: "client", summary: "Shows the merge button.",
      files: [{ path: "src/client/features/cleanline/tabs.ts", startLine: 38, endLine: 85 }] },
    { id: "merge-route", label: "Merge route", kind: "route", delta: "added", lane: "server", files: [{ path: "src/server/http/routes/cleanline.ts" }] },
    { id: "merge-head", label: "mergeHead", kind: "function", delta: "modified", lane: "server", files: [] },
  ],
  edges: [
    { id: "tab-to-route", from: "queue-tab", to: "merge-route", kind: "http", delta: "modified", label: "POST pr, sha" },
    { id: "route-to-merge", from: "merge-route", to: "merge-head", kind: "call", delta: "modified", label: "mergeHead(n, sha)" },
  ],
  flows: [{ id: "pinned-merge", title: "Merging the head", delta: "modified",
    participants: [{ node: "queue-tab" }, { node: "merge-route" }, { node: "merge-head" }],
    messages: [
      { id: "confirm", from: "queue-tab", to: "merge-route", label: "POST /api/cleanline/merge", kind: "sync", delta: "modified",
        payload: { request: { type: "MergeBody", shape: "{ pr: number; sha: string }", sample: { pr: 44, sha: HEAD }, before: { pr: 44 } } } },
      { id: "recheck", from: "merge-route", to: "merge-head", label: "mergeHead(n, sha)", kind: "sync", delta: "modified" },
    ] }],
  views: [
    { id: "overview", title: "Architecture", lens: "architecture", scope: { kind: "all" }, defaultOpen: true },
    { id: "sequence", title: "Pinned merge", lens: "data-flow", scope: { kind: "selection", flows: ["pinned-merge"] } },
  ],
  walkthrough: { steps: [
    { id: "sha", heading: "Merge now sends the sha", body: "The button posts the head sha.", stage: { kind: "flow", flow: "pinned-merge" },
      focus: { kind: "selection", messages: ["confirm"] } },
    { id: "route", heading: "Merge route added", body: "It checks the sha.", stage: { kind: "view", view: "overview" },
      focus: { kind: "selection", nodes: ["merge-route", "merge-head"] } },
    { id: "all", heading: "Two parts changed, one added", body: "Across two lanes." },
  ] },
};

export const LENS_READ = {
  nodeId: "card-lease", executionId: "ex0193", repository: "pletor/agent-office", number: 44, prState: "open", current: true,
  by: "agent:worker", createdAt: "2026-10-22T12:00:00Z",
  lens: { kind: "pr", prNumber: 44, headSha: HEAD, validatedAt: "2026-10-22T11:50:00Z", spec: LENS_SPEC },
  area: null,
};
