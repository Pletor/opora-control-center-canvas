import { describe, expect, it } from "vitest";
import {
  addApprovalItem,
  cleanNote,
  markPending,
  markSending,
  parseApproval,
  pendingApprovals,
  resolveApproval,
  resolveApprovalItem,
  routeLabel,
  ROUTE_LABEL,
  statusWord,
  summaryLines,
  targetScope,
  targetTitle,
} from "./approval";

const EVENT = {
  seq: 7,
  type: "approval",
  approvalId: "a1",
  tool: "Bash",
  reason: "Zapíše spec karty n1",
  input: {
    route: "/api/node-spec",
    project: "p",
    workspace: "w",
    node: "n1",
    script: "x/opora_write.py",
    payloadSummary: 'node: "n1" · expected_revision: 3 · fields: objekt {goal, acceptance}',
  },
};

describe("parseApproval", () => {
  it("rozparsuje cíl zápisu z události", () => {
    const approval = parseApproval(EVENT)!;
    expect(approval).toMatchObject({ id: "a1", tool: "Bash", auto: false, status: "pending", reason: "Zapíše spec karty n1" });
    expect(approval.target).toEqual(EVENT.input);
    expect(targetTitle(approval.target!)).toBe("Zadání karty (goal, non-goals, acceptance) · karta n1");
    expect(targetScope(approval.target!)).toBe("projekt p · workspace w · POST /api/node-spec");
    expect(summaryLines(approval.target!.payloadSummary)).toEqual(['node: "n1"', "expected_revision: 3", "fields: objekt {goal, acceptance}"]);
  });

  it("automatické zamítnutí nemá cíl, jen souhrn nástroje", () => {
    const approval = parseApproval({ approvalId: "a2", tool: "Edit", auto: true, input: { summary: "" }, reason: "Jen přes opora_write.py." })!;
    expect(approval.target).toBeNull();
    expect(approval.auto).toBe(true);
    expect(statusWord(resolveApproval(approval, { decision: "deny", auto: true }))).toBe("Zamítnuto automaticky");
  });

  it("bez approvalId nebo s cestou mimo /api/ nic nevznikne", () => {
    expect(parseApproval({ type: "approval" })).toBeNull();
    expect(parseApproval({ approvalId: "a3", input: { route: "evil" } })!.target).toBeNull();
  });

  it("každá cesta brány zápisu má jméno, nic navíc", () => {
    // Zrcadlo `WRITE_ROUTES` z backend/claude_code/assistant/approvals.py; změna brány = změna tady.
    const gate = ["/api/desktop-v3/lease", "/api/desktop-v3/realize-source", "/api/canvas-layout", "/api/desktop-v3/assignment-snapshot",
      "/api/canvas-versions", "/api/desktop-v3/rule", "/api/desktop-v3/decision", "/api/graph", "/api/node-spec", "/api/node-text",
      "/api/desktop-v3/state", "/api/desktop-v3/block", "/api/desktop-v3/agent-workspace", "/api/desktop-v3/agent-output",
      "/api/canvas-plan", "/api/desktop-v3/pipeline", "/api/brief-vault"];
    expect(Object.keys(ROUTE_LABEL).sort()).toEqual([...gate].sort());
    for (const route of ["/api/desktop-v3/node", "/api/graph/positions", "/api/project-architecture"]) expect(routeLabel(route)).toBe(route);
  });

  it("neznámá cesta se ukáže sama", () => {
    expect(routeLabel("/api/graph")).toBe("Plátno: karty a vazby");
    expect(routeLabel("/api/jina")).toBe("/api/jina");
  });
});

describe("rozhodnutí", () => {
  it("pending → sending → povoleno; chyba vrátí pending", () => {
    const approval = parseApproval(EVENT)!;
    const sending = markSending(approval);
    expect(sending.status).toBe("sending");
    expect(markPending(sending).status).toBe("pending");
    expect(statusWord(resolveApproval(sending, { decision: "allow" }))).toBe("Povoleno");
  });

  it("zamítnutí nese poznámku a timeout", () => {
    const denied = resolveApproval(parseApproval(EVENT)!, { decision: "deny", note: "Jinou kartu." });
    expect(denied).toMatchObject({ status: "denied", note: "Jinou kartu." });
    const late = resolveApproval(parseApproval({ ...EVENT })!, { decision: "deny", auto: true, timeout: true });
    expect(statusWord({ ...late, auto: true })).toBe("Zamítnuto: bez odpovědi do 10 min");
  });

  it("poznámka se ořízne a prázdná se neposílá", () => {
    expect(cleanNote("  ")).toBeUndefined();
    expect(cleanNote("  Ne. ")).toBe("Ne.");
    expect(cleanNote("x".repeat(3000))).toHaveLength(2000);
  });
});

describe("položky konverzace", () => {
  it("přidá žádost jednou a uzavře ji", () => {
    const once = addApprovalItem([], EVENT, false);
    expect(addApprovalItem(once, EVENT, false)).toBe(once);
    expect(pendingApprovals(once).map((a) => a.id)).toEqual(["a1"]);
    const closed = resolveApprovalItem(once, { approvalId: "a1", decision: "allow" });
    expect(pendingApprovals(closed)).toEqual([]);
    expect(closed[0]).toMatchObject({ kind: "approval", approval: { status: "allowed" } });
  });

  it("při přehrání bufferu rozhodnutá žádost zmizí, čekající zůstane", () => {
    const replayed = addApprovalItem([], EVENT, true);
    expect(replayed[0]).toMatchObject({ replayed: true });
    expect(resolveApprovalItem(replayed, { approvalId: "a1", decision: "deny" }, true)).toEqual([]);
    // Živé rozhodnutí obnovené karty ji uzavře, ne smaže.
    expect(resolveApprovalItem(replayed, { approvalId: "a1", decision: "deny" })[0]).toMatchObject({ approval: { status: "denied" } });
  });
});
