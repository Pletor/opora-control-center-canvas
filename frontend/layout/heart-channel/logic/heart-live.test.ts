import { describe, expect, it } from "vitest";
import type { ActivityEntry } from "@/editor/canvas/activity-log/logic/activity-log";
import { batchRange, heartStepsQuery, inputLabel, liveLine, stepRows, stepText, wakeReason } from "./heart-live";

function entry(id: number, extra: Partial<ActivityEntry> = {}): ActivityEntry {
  return {
    id, at: "2026-10-31T10:00:00+00:00", actor: "agent", agent: "heart", method: "POST", path: "/api/gate/tickets",
    project: "p", workspace: "w", nodeIds: [], status: 201, summary: "", ...extra,
  };
}

describe("co srdce probudilo", () => {
  it.each([
    [{ type: "message", text: "Přidej kontakty." }, "zpráva člověka"],
    [{ type: "message", text: "ODPOVĚĎ ČLOVĚKA na t1: ano" }, "odpověď na otázku"],
    [{ type: "merged", pr: 42, nodeId: "n1" }, "sloučení PR #42"],
    [{ type: "merged", pr: null }, "lokální sloučení"],
    [{ type: "ticket", kind: "ask", ticketId: "t1" }, "otázka pracovníka"],
    [{ type: "ticket", kind: "neznámý" }, "lístek pracovníka"],
    [{ type: "commits" }, "nové commity"],
    [{ type: "něco" }, "událost brány"],
  ])("%j → %s", (input, label) => expect(inputLabel(input)).toBe(label));

  it("první vstup a počet dalších; bez vstupů dohánění", () => {
    expect(wakeReason([{ type: "message", text: "a" }, { type: "commits" }, { type: "workFailed" }])).toBe("zpráva člověka + 2 další");
    expect(wakeReason([])).toBe("dohánění vstupů");
  });

  it("řádek běžící dávky nese místní čas začátku a důvod", () => {
    const startedAt = new Date(2026, 9, 31, 11, 51).toISOString();
    expect(liveLine({ startedAt, inputs: [{ type: "merged", pr: 7 }] })).toBe("Pracuje od 11:51 · probudilo: sloučení PR #7");
    expect(liveLine({ startedAt: "?", inputs: [] })).toBe("Pracuje · probudilo: dohánění vstupů");
  });
});

describe("rozsah a dotaz kroků", () => {
  it("skončená dávka: od začátku `at` po konec podle trvání a sekundu navíc", () => {
    expect(batchRange({ at: "2026-10-31T10:00:00Z", durationMs: 90_000 }))
      .toEqual({ since: "2026-10-31T10:00:00Z", until: "2026-10-31T10:01:31.000Z" });
    expect(batchRange({ at: "2026-10-31T10:00:00Z" })).toBeNull();
    expect(batchRange({ at: "x", durationMs: 1 })).toBeNull();
  });

  it("dotaz jen na zápisy srdce v projektu", () => {
    const query = new URL(heartStepsQuery("p 1", { since: "2026-10-31T10:00:00Z" }), "http://x");
    expect(query.pathname).toBe("/api/activity-log");
    expect(Object.fromEntries(query.searchParams)).toEqual({
      project: "p 1", actor: "agent", agent: "heart", since: "2026-10-31T10:00:00Z", limit: "100",
    });
    expect(heartStepsQuery("p", { since: "a", until: "b" })).toContain("until=b");
  });
});

describe("kroky srdce", () => {
  it("věta z popisku akce, konce cesty a operace", () => {
    expect(stepText({ path: "/api/gate/tickets", summary: "body,title" })).toBe("Lístek brány");
    expect(stepText({ path: "/api/oporahub/graph-proposals/g1/accept", summary: "" })).toBe("Přijetí návrhu");
    expect(stepText({ path: "/api/desktop-v3/block", summary: "nodeId,op op=addBlock" })).toBe("Blok karty · addBlock");
  });

  it("nejnovější nahoře, čtení vynechá, jména karet z grafu a selhání u ne-2xx", () => {
    const rows = stepRows(
      [entry(1, { nodeIds: ["n1", "n9"] }), entry(3, { method: "GET" }), entry(2, { status: 409, path: "/api/brain/heart/ask" })],
      [{ id: "n1", name: "Kontakty" }],
    );
    expect(rows.map((row) => [row.key, row.text, row.cards, row.failed])).toEqual([
      [2, "Otázka pro vás", [], true],
      [1, "Lístek brány", ["Kontakty", "n9"], false],
    ]);
  });
});
