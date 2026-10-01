import { describe, expect, it } from "vitest";
import type { OverviewModel } from "@/editor/node-detail/agent-workspace/logic/agent-overview";
import type { OverviewEntry } from "./agent-summary";
import { markLoading, nextStale, staleIds, worksFrom } from "./chapter-queue";

describe("chapter-queue – levný souhrn", () => {
  it("přečte položky odpovědi a příznak read-only", () => {
    const parsed = worksFrom({
      readOnly: false,
      items: {
        a: { filled: 3, by: "agent", updatedAt: "2026-09-17T10:00:00Z" },
        b: { filled: 0, by: "human", updatedAt: "" },
      },
    });
    expect(parsed).toEqual({
      readOnly: false,
      works: {
        a: { filled: 3, by: "agent", updatedAt: "2026-09-17T10:00:00Z" },
        b: { filled: 0, by: "human", updatedAt: "" },
      },
    });
  });

  it("neplatné položky vynechá, neznámého autora čte jako člověka", () => {
    const parsed = worksFrom({
      readOnly: true,
      items: { bad: { by: "agent" }, nan: { filled: Number.NaN }, odd: { filled: 2.7, by: "robot", updatedAt: 5 }, list: [] },
    });
    expect(parsed).toEqual({ readOnly: true, works: { odd: { filled: 2, by: "human", updatedAt: "" } } });
  });

  it("nesmyslná odpověď dá prázdný souhrn", () => {
    expect(worksFrom(null)).toEqual({ readOnly: false, works: {} });
    expect(worksFrom({ items: [] })).toEqual({ readOnly: false, works: {} });
  });
});

describe("chapter-queue – fronta", () => {
  const loaded = new Map([["a", 1], ["b", 0], ["err", 1]]);

  it("na řadě je první rozbalené id bez záznamu z aktuální generace", () => {
    expect(nextStale(["a", "b", "c"], loaded, 1)).toBe("b");
    expect(nextStale(["a", "err"], loaded, 1)).toBeNull();
    expect(nextStale([], loaded, 1)).toBeNull();
    expect(nextStale(["a", "err"], loaded, 2)).toBe("a");
  });

  it("staleIds vrací všechny čekající v pořadí kapitol", () => {
    expect(staleIds(["c", "a", "b"], loaded, 1)).toEqual(["c", "b"]);
    expect(staleIds(["a"], loaded, 1)).toEqual([]);
  });

  it("markLoading nechá starý přehled vidět a nová id založí bez přehledu", () => {
    const model = { path: ["x"] } as unknown as OverviewModel;
    const entries: Record<string, OverviewEntry> = {
      a: { status: "ready", overview: model },
      keep: { status: "ready", overview: null },
    };
    const next = markLoading(entries, ["a", "new"]);
    expect(next).toEqual({
      a: { status: "loading", overview: model },
      new: { status: "loading", overview: null },
      keep: { status: "ready", overview: null },
    });
    expect(entries.a.status).toBe("ready");
  });

  it("markLoading bez změny vrátí stejný objekt", () => {
    const entries: Record<string, OverviewEntry> = { a: { status: "loading", overview: null } };
    expect(markLoading(entries, ["a"])).toBe(entries);
    expect(markLoading(entries, [])).toBe(entries);
  });
});
