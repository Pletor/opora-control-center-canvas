import { describe, expect, it } from "vitest";
import type { OverviewModel } from "@/editor/node-detail/agent-workspace/logic/agent-overview";
import type { CanvasNode } from "@/shared/types/logic/types";
import {
  SUMMARY_FILTERS, actorLabel, chapterWork, filterRows, gapsLabel, isRowLocked, memoryTitle, nextActionIcon, nextRank,
  pendingCount, relativeTime, sortRows, summaryHeadline, summaryRows, workStateOf,
  type OverviewEntry, type SummaryRow,
} from "./agent-summary";

function node(id: string, kind: CanvasNode["kind"] = "node"): CanvasNode {
  return { id, parentId: "layer", kind, name: `Karta ${id}`, purpose: "", x: 0, y: 0 };
}

function overview(overrides: {
  communication?: Partial<OverviewModel["communication"]>;
  verification?: Partial<OverviewModel["verification"]>;
  readOnlyReason?: OverviewModel["readOnlyReason"];
  work?: Partial<OverviewModel["work"]>;
} = {}): OverviewModel {
  return {
    path: [],
    work: { state: "empty", updatedAt: "", filled: 0, total: 5, ...overrides.work },
    communication: { available: true, awaitingReceipt: 0, needsClarification: 0, openQuestions: 0, hasMore: false, ...overrides.communication },
    verification: { goal: "present", dod: "present", gaps: 0, ...overrides.verification },
    nextAction: { label: "Pokračujte.", kind: "follow-harness" },
    safety: { modelInvocation: false, automaticAck: false, ownershipTransfer: false },
    readOnlyReason: overrides.readOnlyReason ?? null,
  };
}

const ready = (model: OverviewModel): OverviewEntry => ({ status: "ready", overview: model });

function row(nodeId: string, overrides: Partial<SummaryRow> = {}): SummaryRow {
  return {
    nodeId, name: nodeId, kind: "node", state: "empty", filled: 0, by: "human", updatedAt: "",
    entry: null, closed: false, ...overrides,
  };
}

const open = () => false;

describe("agent-summary – řádky", () => {
  it("workStateOf: bez souhrnu nebo s nulou je prázdná, jinak podle autora", () => {
    expect(workStateOf(undefined)).toBe("empty");
    expect(workStateOf({ filled: 0, by: "agent", updatedAt: "x" })).toBe("empty");
    expect(workStateOf({ filled: 2, by: "agent", updatedAt: "" })).toBe("agent");
    expect(workStateOf({ filled: 1, by: "human", updatedAt: "" })).toBe("human");
  });

  it("summaryRows drží pořadí dětí, bere jen rozbalené a vynechá komentáře", () => {
    const children = [node("c"), node("k", "comment"), node("a", "sector"), node("b", "area"), node("z")];
    const rows = summaryRows(children, new Set(["a", "c", "k", "b"]), {}, {}, open);
    expect(rows.map((item) => item.nodeId)).toEqual(["c", "a", "b"]);
    expect(rows.map((item) => item.kind)).toEqual(["node", "sector", "area"]);
  });

  it("summaryRows skládá levný souhrn, brief a uzavření", () => {
    const entry = ready(overview());
    const rows = summaryRows(
      [node("a"), node("b")], new Set(["a", "b"]),
      { a: { filled: 3, by: "agent", updatedAt: "2026-09-17T10:00:00Z" } },
      { a: entry },
      (id) => id === "b",
    );
    expect(rows[0]).toEqual({
      nodeId: "a", name: "Karta a", kind: "node", state: "agent", filled: 3, by: "agent",
      updatedAt: "2026-09-17T10:00:00Z", entry, closed: false,
    });
    expect(rows[1]).toMatchObject({ state: "empty", filled: 0, by: "human", updatedAt: "", entry: null, closed: true });
  });

  it("když levný souhrn kartu nezná, vezme práci z načteného briefu", () => {
    const entry = ready(overview({ work: { state: "agent", filled: 4, updatedAt: "2026-09-17T09:00:00Z" } }));
    const [only] = summaryRows([node("a")], new Set(["a"]), {}, { a: entry }, open);
    expect(only).toMatchObject({ state: "agent", filled: 4, by: "agent", updatedAt: "2026-09-17T09:00:00Z" });
  });

  it("chapterWork: souhrn, jinak brief, jinak neznámo", () => {
    const works = { a: { filled: 2, by: "human" as const, updatedAt: "t" } };
    const overviews = {
      a: ready(overview({ work: { state: "agent", filled: 5 } })),
      b: ready(overview({ work: { state: "empty", filled: 0, updatedAt: "" } })),
      c: { status: "error" as const, overview: null },
    };
    expect(chapterWork("a", works, overviews)).toEqual({ filled: 2, by: "human", updatedAt: "t" });
    expect(chapterWork("b", works, overviews)).toEqual({ filled: 0, by: "human", updatedAt: "" });
    expect(chapterWork("c", works, overviews)).toBeUndefined();
    expect(chapterWork("x", works, overviews)).toBeUndefined();
  });

  it("levný souhrn má přednost před briefem", () => {
    const entry = ready(overview({ work: { state: "agent", filled: 4 } }));
    const [only] = summaryRows([node("a")], new Set(["a"]), { a: { filled: 1, by: "human", updatedAt: "" } }, { a: entry }, open);
    expect(only).toMatchObject({ state: "human", filled: 1, by: "human" });
  });
});

describe("agent-summary – komunikace a zámek", () => {
  it("pendingCount sčítá potvrzení, upřesnění a otázky", () => {
    expect(pendingCount(overview({ communication: { awaitingReceipt: 2, needsClarification: 1, openQuestions: 3 } }))).toBe(6);
    expect(pendingCount(overview())).toBe(0);
  });

  it("pendingCount bez briefu nebo s nedostupnou komunikací je 0", () => {
    expect(pendingCount(null)).toBe(0);
    expect(pendingCount(overview({ communication: { available: false, awaitingReceipt: 5 } }))).toBe(0);
  });

  it("isRowLocked: uzavřená karta nebo důvod z briefu", () => {
    expect(isRowLocked(row("a"))).toBe(false);
    expect(isRowLocked(row("a", { closed: true }))).toBe(true);
    expect(isRowLocked(row("a", { entry: ready(overview({ readOnlyReason: "main" })) }))).toBe(true);
    expect(isRowLocked(row("a", { entry: { status: "error", overview: null } }))).toBe(false);
  });
});

describe("agent-summary – filtr", () => {
  const rows = [
    row("agent", { state: "agent", entry: ready(overview({ communication: { openQuestions: 1 } })) }),
    row("human", { state: "human" }),
    row("empty"),
    row("closed", { state: "agent", closed: true }),
    row("main", { state: "human", entry: ready(overview({ readOnlyReason: "main" })) }),
    row("offline", { entry: ready(overview({ communication: { available: false, needsClarification: 2 } })) }),
  ];
  const ids = (list: SummaryRow[]) => list.map((item) => item.nodeId);

  it("nabízí šest filtrů v pevném pořadí", () => {
    expect(SUMMARY_FILTERS.map((item) => item.label)).toEqual(["Vše", "Čeká na mě", "Agent", "Člověk", "Prázdné", "Zamčené"]);
  });

  it("každý filtr vrátí jen své řádky v původním pořadí", () => {
    expect(ids(filterRows(rows, "all"))).toEqual(ids(rows));
    expect(ids(filterRows(rows, "waiting"))).toEqual(["agent"]);
    expect(ids(filterRows(rows, "agent"))).toEqual(["agent", "closed"]);
    expect(ids(filterRows(rows, "human"))).toEqual(["human", "main"]);
    expect(ids(filterRows(rows, "empty"))).toEqual(["empty", "offline"]);
    expect(ids(filterRows(rows, "locked"))).toEqual(["closed", "main"]);
  });

  it("filtr nemění vstupní pole", () => {
    const copy = rows.slice();
    filterRows(rows, "all").pop();
    expect(rows).toEqual(copy);
  });
});

describe("agent-summary – řazení", () => {
  it("nextRank: cíl → hotovo → mezery → čeká → ostatní → zamčené; bez briefu 4", () => {
    expect(nextRank(row("a", { entry: ready(overview({ verification: { goal: "missing", dod: "missing", gaps: 2 } })) }))).toBe(0);
    expect(nextRank(row("a", { entry: ready(overview({ verification: { dod: "missing", gaps: 2 } })) }))).toBe(1);
    expect(nextRank(row("a", { entry: ready(overview({ verification: { gaps: 1 } })) }))).toBe(2);
    expect(nextRank(row("a", { entry: ready(overview({ communication: { awaitingReceipt: 1 } })) }))).toBe(3);
    expect(nextRank(row("a", { entry: ready(overview()) }))).toBe(4);
    expect(nextRank(row("a"))).toBe(4);
    expect(nextRank(row("a", { entry: { status: "loading", overview: null } }))).toBe(4);
    expect(nextRank(row("a", { closed: true, entry: ready(overview({ verification: { goal: "missing" } })) }))).toBe(5);
    expect(nextRank(row("a", { entry: ready(overview({ readOnlyReason: "main" })) }))).toBe(5);
  });

  it("sortRows(next) řadí podle naléhavosti a stejné pořadí nechá z plátna", () => {
    const rows = [
      row("locked", { closed: true }),
      row("plain-1"),
      row("waiting", { entry: ready(overview({ communication: { openQuestions: 2 } })) }),
      row("no-goal-1", { entry: ready(overview({ verification: { goal: "missing" } })) }),
      row("plain-2", { entry: ready(overview()) }),
      row("gaps", { entry: ready(overview({ verification: { gaps: 3 } })) }),
      row("no-dod", { entry: ready(overview({ verification: { dod: "missing" } })) }),
      row("no-goal-2", { entry: ready(overview({ verification: { goal: "missing" } })) }),
    ];
    expect(sortRows(rows, "next").map((item) => item.nodeId)).toEqual([
      "no-goal-1", "no-goal-2", "no-dod", "gaps", "waiting", "plain-1", "plain-2", "locked",
    ]);
  });

  it("sortRows(canvas) vrátí kopii v pořadí plátna", () => {
    const rows = [row("b"), row("a", { closed: true }), row("c")];
    const sorted = sortRows(rows, "canvas");
    expect(sorted.map((item) => item.nodeId)).toEqual(["b", "a", "c"]);
    expect(sorted).not.toBe(rows);
  });
});

describe("agent-summary – čas a popisky", () => {
  const now = new Date("2026-09-17T12:00:00Z");
  const ago = (ms: number) => new Date(now.getTime() - ms).toISOString();
  const MIN = 60_000;
  const HOUR = 60 * MIN;
  const DAY = 24 * HOUR;

  it("relativeTime: prázdné a neplatné datum je pomlčka", () => {
    expect(relativeTime("", now)).toBe("–");
    expect(relativeTime("není datum", now)).toBe("–");
  });

  it("relativeTime: minuty, hodiny, včera", () => {
    expect(relativeTime(ago(0), now)).toBe("právě teď");
    expect(relativeTime(ago(59_000), now)).toBe("právě teď");
    expect(relativeTime(ago(-5 * MIN), now)).toBe("právě teď");
    expect(relativeTime(ago(MIN), now)).toBe("před 1 min");
    expect(relativeTime(ago(59 * MIN + 59_000), now)).toBe("před 59 min");
    expect(relativeTime(ago(HOUR), now)).toBe("před 1 h");
    expect(relativeTime(ago(23 * HOUR + 59 * MIN), now)).toBe("před 23 h");
    expect(relativeTime(ago(DAY), now)).toBe("včera");
    expect(relativeTime(ago(2 * DAY - MIN), now)).toBe("včera");
  });

  it("relativeTime: dny s českým tvarem a starší datum", () => {
    expect(relativeTime(ago(2 * DAY), now)).toBe("před 2 dny");
    expect(relativeTime(ago(4 * DAY + HOUR), now)).toBe("před 4 dny");
    expect(relativeTime(ago(5 * DAY), now)).toBe("před 5 dní");
    expect(relativeTime(ago(6 * DAY + 23 * HOUR), now)).toBe("před 6 dní");
    expect(relativeTime("2026-09-03T12:00:00Z", now)).toBe("3. 9. 2026");
    expect(relativeTime("2025-01-15T12:00:00Z", now)).toBe("15. 1. 2025");
  });

  it("actorLabel a nextActionIcon", () => {
    expect(actorLabel("human")).toBe("člověk");
    expect(actorLabel("agent")).toBe("agent");
    expect(nextActionIcon("request-context")).toBe("target");
    expect(nextActionIcon("follow-harness")).toBe("play");
    expect(nextActionIcon("read-only")).toBe("lock");
    expect(nextActionIcon("")).toBe("arrow-right");
    expect(nextActionIcon("neznámý")).toBe("arrow-right");
  });

  it("memoryTitle vyjmenuje pět polí a počet drží v rozsahu", () => {
    const labels = "Rámec a směr, Postup, Co se nepovedlo, Úspěšné opravy, Předávka";
    expect(memoryTitle(3)).toBe(`Paměť: vyplněno 3 z 5 polí (${labels})`);
    expect(memoryTitle(0)).toBe(`Paměť: vyplněno 0 z 5 polí (${labels})`);
    expect(memoryTitle(9)).toContain("vyplněno 5 z 5");
    expect(memoryTitle(-1)).toContain("vyplněno 0 z 5");
  });

  it("gapsLabel a summaryHeadline skloňují", () => {
    expect([0, 1, 2, 4, 5].map(gapsLabel)).toEqual(["0 mezer", "1 mezera", "2 mezery", "4 mezery", "5 mezer"]);
    expect(summaryHeadline(1, 1)).toBe("1 rozbalená karta · 1 čeká na tebe");
    expect(summaryHeadline(3, 2)).toBe("3 rozbalené karty · 2 čekají na tebe");
    expect(summaryHeadline(6, 5)).toBe("6 rozbalených karet · 5 čeká na tebe");
    expect(summaryHeadline(0, 0)).toBe("0 rozbalených karet · nic na tebe nečeká");
  });
});
