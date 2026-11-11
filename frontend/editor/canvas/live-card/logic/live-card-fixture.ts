// Fixtura odpovědi live-card pro testy: plná karta v běhu a holá karta, kde je skoro všechno null.
import type { LiveCard } from "./live-card-types";

export const LIVE_CARD_FULL: LiveCard = {
  nodeId: "pay", title: "Přijmout platbu", kind: "Logika", crumbs: ["Prodej kurzu", "M2 Lze zaplatit"], state: "bud", progress: 72,
  pills: [{ text: "srdce teď řeší", tone: "heart" }],
  truths: {
    vision: { source: "/api/desktop-v3/node-brief", items: [{ text: "Platba přes FAPI", status: "ok" }, { text: "Neplatný podpis = 401", status: "miss" }] },
    mirror: { available: true, source: "/api/oporahub/live-card?nodeId=pay#mirror", counts: { matched: 2, missing: 1, extra: 1 },
      evidence: { commit: "9b10d44e1f", at: "2026-11-11T14:30:00Z" }, items: [
        { kind: "route", name: "POST /api/fapi/webhook", path: "backend/api/fapi.py", line: 12, status: "ok", text: "webhook" },
        { kind: "symbol", name: "verifySignature()", path: "backend/fapi_sig.py", line: null, status: "ok", text: "" },
        { kind: "test", name: "6 testů", path: "", line: null, status: "miss", text: "testy webhooku chybí" },
        { kind: "file", name: "Popup.tsx", path: "src/marketing/Popup.tsx", status: "bad", text: "karta ho nečeká" }] },
    reality: { source: "/api/pletor/linie/trace/OP-1", items: [{ text: "Objednávka uloží stav", status: "ok" }], sha: "a1c3e9" },
    future: { available: true, verdict: "blocked", works: [{ mark: "OP-1", branch: "feat/fapi", target: "main", changed: ["backend/api/fapi.py", "backend/fapi_sig.py"],
      conflicts: ["backend/api/fapi.py"], impacts: [{ nodeId: "acc", name: "Přístup člena", via: "používá", paths: [] }],
      overlaps: [{ nodeId: "cfg", mark: "OP-2", branch: "feat/cfg", paths: ["backend/fapi_sig.py"] }] }] },
  },
  edges: [{ edgeId: "e1", dir: "out", relation: "používá", carries: "payment.paid", other: { nodeId: "acc", title: "Přístup člena", state: "seed" }, last: null },
    { edgeId: "e2", dir: "in", relation: "sdílí kód", carries: null, other: { nodeId: "cfg", title: "Konfigurace", state: "leaf" }, last: null }],
  flow: { source: "page-plan logic[].flow", pageId: "p1", elementId: "el1", name: "Platba", inputs: ["FAPI"], steps: [{ name: "Webhook" }, "Podpis"], outputs: ["payment.paid"], conditions: ["podpis platný"], dataTo: [] },
  output: { source: "/api/linie/preview", captures: [{ label: "box", url: "/cap/box.png" }], preview: { url: "http://127.0.0.1:8812", status: "running" } },
  linie: { source: "/api/pletor/linie/trace/OP-1", ticketId: "OP-1", mark: "OP-1", branch: "feat/fapi", pr: 412,
    axes: [{ name: "Práce", state: "ok", text: "hotovo" }, { name: "Přijetí", state: "wait", text: "čeká na člověka" }], commits: [{ sha7: "9b10d44", title: "fapi webhook" }], gaps: [] },
  runs: [{ executionId: "x2", at: "2026-11-11T14:30:00Z", state: "done", tests: { passed: 6, total: 6 }, costUsd: 0.04 },
    { executionId: "x1", at: "2026-11-11T14:00:00Z", state: "failed", tests: { passed: 1, total: 6 }, costUsd: 0.02 }],
  cost: { totalUsd: 0.16, budgetUsd: 0.5 },
  recent: [{ at: "2026-11-11T14:31:00Z", actor: "heart", kind: "worker.message", text: "doplň member_id", source: "/api/oporahub/events" },
    { at: "2026-11-11T14:05:00Z", actor: "agent:codex-3", kind: "lease.claimed", text: "převzato", source: "/api/oporahub/events" }],
  decisions: [{ text: "Zvoleno A: webhook + podpis", source: "/api/oporahub/decisions" }],
  children: [{ nodeId: "k1", title: "Webhook endpoint", state: "leaf", progress: 100 }],
  next: { text: "doplnit member_id do payment.paid", why: "Přístup na něm stojí." },
  heart: { at: "2026-11-11T14:31:00Z", severity: "course", text: "Doplň member_id." },
  agent: {
    address: "opora://card/OP-1", lease: { holder: "worker:codex-3", until: "2026-11-11T14:52:00Z" }, revision: 7,
    reads: [{ layer: "#souhrn", method: "GET", url: "/api/desktop-v3/node-brief?nodeId=pay&layer=souhrn", size: "≈ 40 tok", exists: true },
      { layer: "#deník", method: "SSE", url: "/api/oporahub/events/stream?nodeId=pay", size: null, exists: true }],
    writes: [{ role: "dělník", method: "POST", url: "/api/desktop-v3/agent-output", what: "kroky, evidence" }],
    triggers: [{ when: "commit s Opora-Mark", then: "přepočet zrcadla" }],
  },
};

export const LIVE_CARD_BARE: LiveCard = {
  nodeId: "seed1", title: "Potvrzovací e-mail", kind: "", crumbs: [], state: "seed", progress: null, pills: [],
  truths: { vision: null, mirror: { available: false, milestone: "F1" }, reality: null, future: null },
  edges: [], flow: null, output: null, linie: null, runs: [], cost: null, recent: [], decisions: [], children: [],
  next: null, heart: null, agent: null,
};
