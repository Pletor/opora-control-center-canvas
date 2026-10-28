import { describe, expect, it } from "vitest";
import {
  actionLabel, activityQuery, appendOlder, dayKey, dayLabel, groupByDay, isFailed, isFullAutonomy, mergeFresh, nodeRefs,
  summaryDetail, tabStats, timeLabel, type ActivityEntry,
} from "./activity-log";

function entry(id: number, at: string, extra: Partial<ActivityEntry> = {}): ActivityEntry {
  return { id, at, actor: "human", agent: "", method: "POST", path: "/api/graph", project: "p", workspace: "main", nodeIds: [], status: 200, summary: "", ...extra };
}
const local = (y: number, m: number, d: number, h = 12, min = 0) => new Date(y, m - 1, d, h, min).toISOString();

describe("actionLabel – lidský název akce z cesty", () => {
  it.each([
    ["/api/desktop-v3/agent-output", "Výstup agenta"],
    ["/api/node-spec", "Zadání karty"],
    ["/api/node-text", "Text karty"],
    ["/api/desktop-v3/block", "Blok karty"],
    ["/api/graph", "Plátno (graf)"],
    ["/api/canvas-plan", "Dávka plánu"],
    ["/api/canvas-versions", "Uložit vše"],
    ["/api/desktop-v3/state", "Stav karet"],
    ["/api/desktop-v3/agent-workspace", "Prostor agenta"],
  ])("%s → %s", (path, label) => expect(actionLabel(path)).toBe(label));

  it("delší předpona vyhrává a podcesta dědí popisek", () => {
    expect(actionLabel("/api/canvas-versions/restore")).toBe("Obnova verze");
    expect(actionLabel("/api/node-text/abc")).toBe("Text karty");
  });

  it("neznámá cesta i podobná předpona zůstane cestou, query se ořízne", () => {
    expect(actionLabel("/api/graphical")).toBe("/api/graphical");
    expect(actionLabel("/api/unknown?x=1")).toBe("/api/unknown");
  });
});

describe("summaryDetail – doplněk ze summary", () => {
  it("vybere druh operace a návrh uzavření, klíče těla vynechá", () => {
    expect(summaryDetail("nodeId,op op=addBlock")).toBe("addBlock");
    expect(summaryDetail("nodeId,output done.proposed=true")).toBe("návrh uzavření");
    expect(summaryDetail("nodeId,output done.proposed=false")).toBe("");
    expect(summaryDetail("")).toBe("");
  });
});

describe("isFailed – stav zápisu", () => {
  it("2xx je úspěch, ostatní selhání", () => {
    expect(isFailed(200)).toBe(false);
    expect(isFailed(204)).toBe(false);
    expect(isFailed(409)).toBe(true);
    expect(isFailed(500)).toBe(true);
    expect(isFailed(0)).toBe(true);
  });
});

describe("čas a dny", () => {
  const now = new Date(2026, 9, 6, 15, 0);
  it("timeLabel je místní HH:MM, neplatný čas prázdný", () => {
    expect(timeLabel(local(2026, 10, 6, 9, 5))).toBe("09:05");
    expect(timeLabel("nesmysl")).toBe("");
  });
  it("dayLabel: Dnes, Včera, jinak datum", () => {
    expect(dayLabel(dayKey(now), now)).toBe("Dnes");
    expect(dayLabel("2026-10-05", now)).toBe("Včera");
    expect(dayLabel("2026-09-30", now)).toBe("30. 9. 2026");
    expect(dayLabel("?", now)).toBe("Neznámý čas");
  });
  it("groupByDay drží pořadí a dělí podle místního dne", () => {
    const groups = groupByDay([entry(3, local(2026, 10, 6, 10)), entry(2, local(2026, 10, 6, 8)), entry(1, local(2026, 10, 4))], now);
    expect(groups.map((group) => [group.label, group.entries.map((item) => item.id)])).toEqual([["Dnes", [3, 2]], ["4. 10. 2026", [1]]]);
  });
});

describe("nodeRefs – jména karet z grafu", () => {
  it("známá karta dostane jméno, neznámá zůstane svým ID", () => {
    expect(nodeRefs(["a", "x"], [{ id: "a", name: "Přihlášení" }])).toEqual([
      { id: "a", name: "Přihlášení", known: true },
      { id: "x", name: "x", known: false },
    ]);
  });
});

describe("activityQuery", () => {
  it("skládá rozsah, aktéra, kartu a stránku", () => {
    expect(activityQuery({ project: "p 1", workspace: "main", actor: "agent" })).toBe("/api/activity-log?project=p+1&workspace=main&actor=agent&limit=100");
    expect(activityQuery({ project: "p", workspace: "w", actor: "human", nodeId: "n1", before: 42, limit: 50 }))
      .toBe("/api/activity-log?project=p&workspace=w&actor=human&limit=50&nodeId=n1&before=42");
  });
});

describe("stránkování", () => {
  it("mergeFresh přiloží nové zápisy bez zdvojení a nechá načtené starší", () => {
    const previous = { entries: [entry(5, "x"), entry(4, "x"), entry(3, "x")], nextBefore: 3 };
    const merged = mergeFresh(previous, { entries: [entry(6, "x"), entry(5, "x")], nextBefore: 5 });
    expect(merged.entries.map((item) => item.id)).toEqual([6, 5, 4, 3]);
    expect(merged.nextBefore).toBe(3);
  });
  it("mergeFresh při mezeře začne znovu od nové stránky", () => {
    const fresh = { entries: [entry(9, "x"), entry(8, "x")], nextBefore: 8 };
    expect(mergeFresh({ entries: [entry(2, "x")], nextBefore: null }, fresh)).toBe(fresh);
  });
  it("appendOlder přidá starší na konec a převezme jejich nextBefore", () => {
    const page = appendOlder({ entries: [entry(5, "x")], nextBefore: 5 }, { entries: [entry(4, "x"), entry(3, "x")], nextBefore: null });
    expect(page.entries.map((item) => item.id)).toEqual([5, 4, 3]);
    expect(page.nextBefore).toBeNull();
  });
  it("tabStats ukáže „+“ u dalších stránek a počet selhání", () => {
    expect(tabStats({ entries: [entry(2, "x", { status: 409 }), entry(1, "x")], nextBefore: 1 })).toEqual({ count: "2+", failed: 1 });
    expect(tabStats({ entries: [], nextBefore: null })).toEqual({ count: "0", failed: 0 });
  });
});

describe("isFullAutonomy – akce z plné autonomie", () => {
  it("jen autonomy: \"full\" se označí", () => {
    expect(isFullAutonomy(entry(1, local(2026, 10, 28), { actor: "agent", autonomy: "full" }))).toBe(true);
    expect(isFullAutonomy(entry(2, local(2026, 10, 28), { actor: "agent" }))).toBe(false);
  });
});
