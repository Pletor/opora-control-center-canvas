import { describe, expect, it } from "vitest";
import type { QueueTask } from "./heart-api";
import { groupQueue, holderLabel } from "./queue";

const task = (taskId: string, status: QueueTask["status"], order = 1, sessionId: string | null = null): QueueTask => ({
  taskId, title: taskId, status, sessionId, nodeId: null, createdBy: "heart", updatedAt: "2026-10-29T10:00:00Z", order, body: { do: "x" },
});

describe("fronta srdce", () => {
  it("skupiny jdou v pořadí ready, assigned, done, failed, cancelled a prázdné vypadnou", () => {
    const groups = groupQueue([task("a", "done"), task("b", "ready", 2), task("c", "ready", 1), task("d", "cancelled")]);
    expect(groups.map((g) => g.status)).toEqual(["ready", "done", "cancelled"]);
    expect(groups[0].tasks.map((t) => t.taskId)).toEqual(["c", "b"]);
    expect(groups[0].label).toBe("Připraveno");
  });

  it("prázdná fronta nemá skupiny", () => {
    expect(groupQueue([])).toEqual([]);
  });

  it("držitel je relace pracovníka, jinak autor úkolu", () => {
    expect(holderLabel(task("a", "assigned", 1, "gs_abcdef123"))).toBe("relace abcdef");
    expect(holderLabel(task("a", "ready"))).toBe("srdce");
    expect(holderLabel({ ...task("a", "ready"), createdBy: "human" })).toBe("člověk");
  });
});
