import { describe, expect, it } from "vitest";
import {
  addLocalUserMessage,
  applyEvent,
  emptyConversation,
  failLocalMessage,
  isBusy,
  loadTranscript,
  type AssistantEvent,
  type Conversation,
} from "./assistant-events";
import { markSending, pendingApprovals, updateApproval } from "./approval";

function run(events: AssistantEvent[], start: Conversation = emptyConversation()): Conversation {
  return events.reduce(applyEvent, start);
}

describe("text_delta a message", () => {
  it("skládá text zprávy z přírůstků a označí ji jako běžící", () => {
    const conv = run([
      { seq: 1, type: "text_delta", messageId: "a", text: "Ahoj " },
      { seq: 2, type: "text_delta", messageId: "a", text: "světe" },
    ]);
    expect(conv.items).toEqual([
      { kind: "message", id: "a", role: "assistant", text: "Ahoj světe", streaming: true, origin: "live" },
    ]);
  });

  it("message se stejným messageId nahradí složený text a nezdvojí ho", () => {
    const conv = run([
      { seq: 1, type: "text_delta", messageId: "a", text: "Ah" },
      { seq: 2, type: "message", role: "assistant", text: "Ahoj hotovo", messageId: "a" },
    ]);
    expect(conv.items).toHaveLength(1);
    expect(conv.items[0]).toMatchObject({ text: "Ahoj hotovo", streaming: false });
  });

  it("message bez messageId se přidá jako nová zpráva", () => {
    const conv = run([{ seq: 4, type: "message", role: "assistant", text: "Hotovo" }]);
    expect(conv.items).toEqual([
      { kind: "message", id: "m4", role: "assistant", text: "Hotovo", streaming: false, origin: "live" },
    ]);
  });

  it("zpráva uživatele odeslaná z UI se potvrzením od serveru nezdvojí", () => {
    const sent = addLocalUserMessage(emptyConversation(), "Co je na plátně?", "local-1");
    const conv = applyEvent(sent, { seq: 1, type: "message", role: "user", text: "Co je na plátně?" });
    expect(conv.items).toHaveLength(1);
    expect(conv.items[0]).toMatchObject({ role: "user", origin: "live" });
  });
});

describe("tool_use a tool_result", () => {
  it("páruje výsledek s voláním podle id", () => {
    const open = run([
      { seq: 1, type: "tool_use", id: "t1", name: "Read", summary: "README.md" },
      { seq: 2, type: "tool_use", id: "t2", name: "Grep", summary: "pattern" },
    ]);
    expect(open.items.map((i) => i.kind === "tool" && i.status)).toEqual(["running", "running"]);
    const done = run(
      [
        { seq: 3, type: "tool_result", id: "t2", ok: true, summary: "3 shody" },
        { seq: 4, type: "tool_result", id: "t1", ok: false, summary: "chybí soubor" },
      ],
      open,
    );
    expect(done.items[0]).toMatchObject({ id: "t1", status: "error", result: "chybí soubor" });
    expect(done.items[1]).toMatchObject({ id: "t2", status: "ok", result: "3 shody" });
  });

  it("výsledek bez známého voláním vytvoří samostatný řádek", () => {
    const conv = run([{ seq: 1, type: "tool_result", id: "x", ok: true, summary: "ok" }]);
    expect(conv.items).toHaveLength(1);
    expect(conv.items[0]).toMatchObject({ kind: "tool", id: "x", status: "ok" });
  });
});

describe("status, error a turn_end", () => {
  it("status mění stav session, neznámý stav ignoruje", () => {
    expect(run([{ seq: 1, type: "status", state: "running" }]).state).toBe("running");
    expect(run([{ seq: 1, type: "status", state: "nesmysl" }]).state).toBe("idle");
  });

  it("error přidá červený řádek a ukončí streamování", () => {
    const conv = run([
      { seq: 1, type: "text_delta", messageId: "a", text: "půl" },
      { seq: 2, type: "error", message: "Limit předplatného" },
    ]);
    expect(conv.state).toBe("error");
    expect(conv.items[0]).toMatchObject({ streaming: false });
    expect(conv.items[1]).toEqual({ kind: "error", id: "e2", text: "Limit předplatného" });
  });

  it("turn_end vrátí stav na idle a zapamatuje si tah", () => {
    const conv = run([
      { seq: 1, type: "status", state: "running" },
      { seq: 2, type: "text_delta", messageId: "a", text: "x" },
      { seq: 3, type: "turn_end", durationMs: 1200, usage: {}, isError: false, numTurns: 2, denied: [{}, {}] },
    ]);
    expect(conv.state).toBe("idle");
    expect(conv.items[0]).toMatchObject({ streaming: false });
    expect(conv.lastTurn).toEqual({ durationMs: 1200, isError: false, numTurns: 2, denied: 2 });
  });

  it("isBusy platí pro běh a čekání na schválení", () => {
    expect(isBusy("running")).toBe(true);
    expect(isBusy("waiting_approval")).toBe(true);
    expect(isBusy("idle")).toBe(false);
  });
});

describe("neznámé a duplicitní události", () => {
  it("neznámý typ stav nemění, jen posune seq", () => {
    const conv = run([{ seq: 1, type: "rate_limit", approvalId: "p" }, { seq: 2, type: "approval_resolved" }]);
    expect(conv.items).toEqual([]);
    expect(conv.lastSeq).toBe(2);
  });

  it("událost s už viděným seq se ignoruje", () => {
    const conv = run([
      { seq: 5, type: "text_delta", messageId: "a", text: "A" },
      { seq: 5, type: "text_delta", messageId: "a", text: "A" },
      { seq: 3, type: "text_delta", messageId: "a", text: "B" },
    ]);
    expect(conv.items[0]).toMatchObject({ text: "A" });
    expect(conv.lastSeq).toBe(5);
  });
});

describe("transcript", () => {
  it("načte historii a navazuje od lastSeq", () => {
    const history = loadTranscript(
      [
        { role: "user", text: "Ahoj" },
        { role: "assistant", text: "Dobrý den" },
      ],
      "idle",
      7,
    );
    expect(history.items.map((i) => i.kind === "message" && [i.role, i.text])).toEqual([
      ["user", "Ahoj"],
      ["assistant", "Dobrý den"],
    ]);
    expect(history.lastSeq).toBe(7);
    const next = applyEvent(history, { seq: 8, type: "text_delta", messageId: "n", text: "Nové" });
    expect(next.items).toHaveLength(3);
    expect(applyEvent(history, { seq: 7, type: "text_delta", messageId: "n", text: "Staré" }).items).toHaveLength(2);
  });

  it("zprávu, která je už v přepisu, nezdvojí opožděná událost", () => {
    const history = loadTranscript([{ role: "assistant", text: "Hotovo" }], "idle", 3);
    const conv = applyEvent(history, { seq: 4, type: "message", role: "assistant", text: "Hotovo" });
    expect(conv.items).toHaveLength(1);
  });
});

describe("odeslání z UI", () => {
  it("odeslání zapne běh a selhání vrátí chybu", () => {
    const sent = addLocalUserMessage(emptyConversation(), "Ahoj", "local-1");
    expect(sent.state).toBe("running");
    const failed = failLocalMessage(sent, "local-1", "Asistent ještě odpovídá.");
    expect(failed.state).toBe("idle");
    expect(failed.items).toEqual([{ kind: "error", id: "e-local-1", text: "Asistent ještě odpovídá." }]);
  });
});

describe("approval a approval_resolved", () => {
  const approval = {
    seq: 3, type: "approval", approvalId: "a1", tool: "Bash", reason: "Zapíše spec",
    input: { route: "/api/node-spec", project: "p", workspace: "w", node: "n1", script: "x/opora_write.py", payloadSummary: "node: \"n1\"" },
  };

  it("approval přidá čekající žádost, approval_resolved ji uzavře", () => {
    const waiting = run([{ seq: 2, type: "status", state: "waiting_approval" }, approval]);
    expect(waiting.state).toBe("waiting_approval");
    expect(pendingApprovals(waiting.items).map((a) => a.id)).toEqual(["a1"]);
    const done = run([{ seq: 4, type: "approval_resolved", approvalId: "a1", decision: "deny", note: "Ne." }, { seq: 5, type: "status", state: "running" }], waiting);
    expect(pendingApprovals(done.items)).toEqual([]);
    expect(done.items[0]).toMatchObject({ kind: "approval", approval: { status: "denied", note: "Ne." } });
    expect(done.state).toBe("running");
  });

  it("při otevření čekajícího úkolu přehraje z bufferu jen čekající žádosti", () => {
    const history = loadTranscript([{ role: "user", text: "Zapiš spec" }], "waiting_approval", 10);
    const old = { ...approval, seq: 1, approvalId: "old" };
    const conv = run([
      old,
      { seq: 2, type: "approval_resolved", approvalId: "old", decision: "allow" },
      { seq: 3, type: "message", role: "assistant", text: "staré" },
      { ...approval, seq: 9 },
    ], history);
    expect(conv.lastSeq).toBe(10);
    expect(conv.items.map((it) => it.kind)).toEqual(["message", "approval"]);
    expect(pendingApprovals(conv.items).map((a) => a.id)).toEqual(["a1"]);
    const live = applyEvent(conv, { seq: 11, type: "approval_resolved", approvalId: "a1", decision: "allow" });
    expect(live.items[1]).toMatchObject({ approval: { status: "allowed" } });
  });

  it("updateApproval změní jen danou žádost", () => {
    const conv = run([approval, { ...approval, seq: 4, approvalId: "a2" }]);
    const next = updateApproval(conv, "a2", markSending);
    expect(next.items.map((it) => it.kind === "approval" && it.approval.status)).toEqual(["pending", "sending"]);
  });
});
