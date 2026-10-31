import { describe, expect, it } from "vitest";
import { FRESH_MS, changeOf, changeWhen, changeWho, isFresh, latestQuery, orderBadge, parseLatest } from "./face-change";

describe("odznak pořadí", () => {
  it("fáze · pozice", () => {
    expect(orderBadge(302)).toBe("3·02");
    expect(orderBadge(1205)).toBe("12·05");
    expect(orderBadge(7)).toBe("0·07");
  });
  it("bez pořadí nic", () => {
    expect(orderBadge(null)).toBeNull();
    expect(orderBadge(undefined)).toBeNull();
    expect(orderBadge(-1)).toBeNull();
    expect(orderBadge(1.5)).toBeNull();
  });
});

describe("kdo · kdy · co", () => {
  it("srdce, člověk a dělník", () => {
    expect(changeWho("agent", "heart")).toEqual({ who: "Srdce", whoKind: "heart" });
    expect(changeWho("human", "")).toEqual({ who: "Vy", whoKind: "human" });
    expect(changeWho("agent", "S.1")).toEqual({ who: "Dělník S.1", whoKind: "agent" });
    expect(changeWho("agent", "agent:codex-2")).toEqual({ who: "Dělník codex-2", whoKind: "agent" });
    expect(changeWho("agent", "agent")).toEqual({ who: "Agent", whoKind: "agent" });
    expect(changeWho("unknown", "")).toEqual({ who: "Agent", whoKind: "agent" });
  });

  it("co: popisek, jinak akce z cesty; neplatný čas = bez řádky", () => {
    const entry = { at: "2026-10-31T10:51:00Z", actor: "agent", agent: "heart", label: "Pořadí 12 karet", path: "/api/oporahub/graph-proposals" };
    expect(changeOf(entry)).toEqual({ at: entry.at, who: "Srdce", whoKind: "heart", what: "Pořadí 12 karet" });
    expect(changeOf({ ...entry, label: "" })?.what).toBe("Návrh grafu");
    expect(changeOf({ ...entry, at: "x" })).toBeNull();
    expect(changeOf(undefined)).toBeNull();
  });

  it("kdy: dnes čas, včera, letos bez roku, jinak datum", () => {
    const now = new Date(2026, 9, 31, 12, 0);
    expect(changeWhen(new Date(2026, 9, 31, 11, 51).toISOString(), now)).toBe("11:51");
    expect(changeWhen(new Date(2026, 9, 30, 23, 0).toISOString(), now)).toBe("včera");
    expect(changeWhen(new Date(2026, 9, 6, 9, 0).toISOString(), now)).toBe("6. 10.");
    expect(changeWhen(new Date(2025, 11, 24, 9, 0).toISOString(), now)).toBe("24. 12. 2025");
    expect(changeWhen("x", now)).toBe("");
  });

  it("čerstvost: mladší než 10 minut", () => {
    const now = Date.parse("2026-10-31T12:00:00Z");
    expect(isFresh("2026-10-31T11:55:00Z", now)).toBe(true);
    expect(isFresh(new Date(now - FRESH_MS).toISOString(), now)).toBe(false);
    expect(isFresh("2026-10-31T13:00:00Z", now)).toBe(false);
    expect(isFresh("x", now)).toBe(false);
  });
});

describe("odpověď latest-by-node", () => {
  it("dotaz a přísné čtení", () => {
    expect(latestQuery("p 1", "w")).toBe("/api/activity-log/latest-by-node?project=p+1&workspace=w");
    expect(parseLatest({ a: { at: "t", actor: "human", agent: "", label: "L", path: "/x" }, b: { actor: "human" }, c: 3 }))
      .toEqual({ a: { at: "t", actor: "human", agent: "", label: "L", path: "/x" } });
    expect(parseLatest(null)).toEqual({});
    expect(parseLatest([1])).toEqual({});
  });
});
