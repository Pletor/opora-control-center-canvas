// Malý platný Lens plánu pro testy a snímek: jedna oblast se dvěma kartami s kódem, jednou jen
// v plánu (odznak „plán“), vazbou z plánu a šedou vazbou „kód“ z Graphify; druhá oblast je předávka.
const HEAD = "a6a28b0c42394e0a00de74d580c95bfc5caf0f60";

export const PLAN_SPEC = {
  schemaVersion: "0.2.0", kind: "graph", title: "Oblast Přihlášení", summary: "Karty oblasti, jejich vazby z plánu a vazby v kódu podle Graphify.",
  lenses: ["architecture"],
  provenance: { repo: { owner: "Pletor", name: "opora-control-center-canvas", host: "github.com" }, base: { sha: HEAD, ref: "main" }, head: { sha: HEAD } },
  lanes: [{ id: "area-login", label: "Přihlášení", order: 0 }, { id: "handoff", label: "Předávky", order: 1 }],
  nodes: [
    { id: "card-form", label: "Formulář přihlášení", kind: "ui", delta: "unchanged", lane: "area-login", summary: "Karta s kódem.",
      files: [{ path: "frontend/app/access-gate/components/AccessGate.tsx", startLine: 1, endLine: 40 }] },
    { id: "card-session", label: "Session API", kind: "route", delta: "unchanged", lane: "area-login", files: [{ path: "backend/api/session.py" }] },
    { id: "card-reset", label: "Obnova hesla", kind: "route", delta: "added", lane: "area-login", summary: "Jen v plánu, kód zatím není.", badges: ["plán"] },
    { id: "area-billing", label: "Oblast Platby", kind: "module", delta: "unchanged", lane: "handoff", summary: "Předávka do jiné oblasti." },
  ],
  edges: [
    { id: "plan-form-session", from: "card-form", to: "card-session", kind: "dependency", delta: "unchanged", label: "plán" },
    { id: "plan-session-reset", from: "card-session", to: "card-reset", kind: "dependency", delta: "added", label: "plán" },
    { id: "code-form-session", from: "card-form", to: "card-session", kind: "call", delta: "unchanged", label: "kód", emphasis: "muted" },
    { id: "handoff-billing", from: "card-session", to: "area-billing", kind: "data", delta: "unchanged", label: "předávka" },
  ],
};

export const PLAN_STATS = { areas: 2, cards: 3, withCode: 2, planned: 1, standalone: 0, unassigned: 1 };

export const PLAN_LENS_RESPONSE = {
  kind: "plan", area: "area-login", digest: "sha256:5f1c0d9e", spec: PLAN_SPEC, stats: PLAN_STATS,
  graphify: { available: true, sourceRevision: HEAD },
};
