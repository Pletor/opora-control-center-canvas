import { describe, expect, it } from "vitest";
import { appendJournal, journalView, unseenCount, whoText } from "./linie-journal";

const page1 = journalView({ events: [
  { id: 3, kind: "linie.accept", at: "2026-11-06T10:00:00Z", by: "human", refs: { ticket: "tk_1", sha: "9c8050f1a2b3" }, data: {} },
  { id: 5, kind: "linie.request.failed", at: "2026-11-06T10:02:00Z", by: "agent:office", refs: { request: "rq_1", ticket: "tk_2" }, data: { k: "attempt", why: "relace spadla" } },
  { id: 6, kind: "linie.deploy", at: "2026-11-06T10:03:00Z", by: "agent:deploy", refs: { env: "staging", sha: "abcdef0123" }, data: {} },
], lastId: 6 });

describe("deník", () => {
  it("událost nese čas, druh slovy, původce, kuličku a větu z odkazů; selhání je označené", () => {
    expect(page1.events.map((e) => [e.id, e.kindText, e.who, e.ticketId, e.text, e.failed])).toEqual([
      [3, "přijetí", "člověk", "tk_1", "9c8050f", false],
      [5, "selhání", "office", "tk_2", "krok attempt · rq_1 · relace spadla", true],
      [6, "nasazení", "deploy", "", "staging · abcdef0", false],
    ]);
    expect([whoText(""), whoText("agent:")]).toEqual(["služba OPORY", "agent"]);
    expect(journalView(null)).toEqual({ events: [], lastId: 0 });
  });
  it("další stránka navazuje podle id bez duplicit; nových se počítá od posledního viděného id", () => {
    const page2 = journalView({ events: [{ id: 6, kind: "linie.deploy", at: "", by: "", refs: {}, data: {} }, { id: 7, kind: "linie.merge.finished", at: "", by: "opora", refs: { ticket: "tk_1", sha: "0be1f77aaaa" }, data: {} }], lastId: 7 });
    const all = appendJournal(page1, page2);
    expect(all.events.map((e) => e.id)).toEqual([3, 5, 6, 7]);
    expect(all.lastId).toBe(7);
    expect([unseenCount(all, 0), unseenCount(all, 5), unseenCount(all, 7)]).toEqual([4, 2, 0]);
    expect(all.events[3]).toMatchObject({ kindText: "merge", who: "služba OPORY", text: "0be1f77" });
  });
});
