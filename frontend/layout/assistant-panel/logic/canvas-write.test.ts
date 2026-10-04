import { describe, expect, it } from "vitest";
import type { AssistantEvent } from "./assistant-events";
import { startWatch, watchEvent } from "./canvas-write";

function run(events: AssistantEvent[], since = 0): number[] {
  let watch = startWatch(since);
  const fired: number[] = [];
  for (const event of events) {
    const r = watchEvent(watch, event);
    watch = r.watch;
    if (r.written) fired.push(event.seq ?? -1);
  }
  return fired;
}

const write = (ok: boolean, decision = "allow"): AssistantEvent[] => [
  { seq: 1, type: "tool_use", id: "t1", name: "Bash" },
  { seq: 2, type: "approval", approvalId: "a1", tool: "Bash", input: {} },
  { seq: 3, type: "approval_resolved", approvalId: "a1", decision },
  { seq: 4, type: "tool_result", id: "t1", ok },
];

describe("povolený zápis na plátno", () => {
  it("allow a úspěšný výsledek ohlásí zápis", () => {
    expect(run(write(true))).toEqual([4]);
  });

  it("zamítnutí ani neúspěch nic nespustí", () => {
    expect(run(write(true, "deny"))).toEqual([]);
    expect(run(write(false))).toEqual([]);
  });

  it("automatické zamítnutí a jiný nástroj se nepočítají", () => {
    expect(run([
      { seq: 1, type: "approval", approvalId: "a1", tool: "Bash", auto: true },
      { seq: 2, type: "approval_resolved", approvalId: "a1", decision: "deny", auto: true },
      { seq: 3, type: "tool_result", id: "x", ok: true },
    ])).toEqual([]);
    expect(run([
      { seq: 1, type: "approval", approvalId: "a1", tool: "Edit" },
      { seq: 2, type: "approval_resolved", approvalId: "a1", decision: "allow" },
      { seq: 3, type: "tool_result", id: "x", ok: true },
    ])).toEqual([]);
  });

  it("výsledek jiného nástroje před zápisem se nezapočte, páruje se podle id", () => {
    expect(run([
      { seq: 1, type: "tool_use", id: "r1", name: "Read" },
      { seq: 2, type: "tool_use", id: "t1", name: "Bash" },
      { seq: 3, type: "approval", approvalId: "a1", tool: "Bash" },
      { seq: 4, type: "approval_resolved", approvalId: "a1", decision: "allow" },
      { seq: 5, type: "tool_result", id: "r1", ok: true },
      { seq: 6, type: "tool_result", id: "t1", ok: true },
    ])).toEqual([6]);
  });

  it("bez spárovaného tool_use platí první výsledek po povolení v témže tahu", () => {
    expect(run([
      { seq: 1, type: "approval", approvalId: "a1", tool: "Bash" },
      { seq: 2, type: "approval_resolved", approvalId: "a1", decision: "allow" },
      { seq: 3, type: "tool_result", id: "z", ok: true },
      { seq: 4, type: "tool_result", id: "y", ok: true },
    ])).toEqual([3]);
    expect(run([
      { seq: 1, type: "approval", approvalId: "a1", tool: "Bash" },
      { seq: 2, type: "approval_resolved", approvalId: "a1", decision: "allow" },
      { seq: 3, type: "turn_end" },
      { seq: 4, type: "tool_result", id: "y", ok: true },
    ])).toEqual([]);
  });

  it("přehrání bufferu starý zápis neohlásí, čekající žádost po povolení ano", () => {
    const old = write(true);
    const pending: AssistantEvent[] = [
      { seq: 5, type: "tool_use", id: "t2", name: "Bash" },
      { seq: 6, type: "approval", approvalId: "a2", tool: "Bash" },
    ];
    const live: AssistantEvent[] = [
      { seq: 7, type: "approval_resolved", approvalId: "a2", decision: "allow" },
      { seq: 8, type: "tool_result", id: "t2", ok: true },
    ];
    expect(run([...old, ...pending, ...live], 6)).toEqual([8]);
  });

  it("opakovaná událost se stejným seq se ohlásí jen jednou", () => {
    const events = write(true);
    expect(run([...events, events[3]])).toEqual([4]);
  });
});
