import { describe, expect, it } from "vitest";
import { authorName, blameRows, blameUrl, historyRows, historyUrl, parseBlame, parseHistory } from "./card-history";

const human = { kind: "human", name: "Martin" }, system = { kind: "orchestrator", name: "system" };
const history = { cardId: "a", acceptedHead: "r2", items: [
  { revisionId: "r1", parentRevision: null, revisionKind: "spec", proposalId: "cs1", proposalKind: "spec", subject: "Cíl",
    author: human, originalAuthor: human, rebasedFrom: null, acceptedBy: human, acceptedAt: "2026-10-20T10:00:00", changedKeys: ["spec:goal"] },
  { revisionId: "r2", parentRevision: "r1", revisionKind: "spec", proposalId: "cs3", proposalKind: "spec", subject: "Přijetí",
    author: system, originalAuthor: { kind: "agent", name: "office" }, rebasedFrom: "cs2", acceptedBy: human,
    acceptedAt: "2026-10-21T10:00:00", changedKeys: ["spec:acceptance"] },
] };

describe("card history and blame", () => {
  it("lists revisions newest first and names the original author of an auto-rebase", () => {
    const rows = historyRows(parseHistory(history));
    expect(rows.map(row => row.revisionId)).toEqual(["r2", "r1"]);
    expect(rows[0]).toMatchObject({ current: true, author: "system (orchestrator)", keys: ["spec:acceptance"] });
    expect(rows[0].rebased).toBe("auto-rebase z cs2 · původně office (agent)");
    expect(rows[1].rebased).toBe("");
  });
  it("maps blame keys to their last revision", () => {
    const blame = parseBlame({ cardId: "a", acceptedHead: "r2", items: [{ ...history.items[1], key: "spec:acceptance" }] });
    expect(blameRows(blame)).toEqual([{ key: "spec:acceptance", revisionId: "r2", short: "r2", author: "office (agent)", acceptedAt: "2026-10-21 10:00" }]);
  });
  it("tolerates author shapes and rejects broken documents", () => {
    expect(authorName("Eva")).toBe("Eva");
    expect(authorName(null)).toBe("neznámý");
    expect(authorName({ kind: "human", name: "Eva" })).toBe("Eva");
    expect(() => parseHistory({ cardId: "a", items: [{}] })).toThrow();
    expect(() => parseBlame({ cardId: "a", items: [{ revisionId: "r" }] })).toThrow();
  });
  it("encodes the card id in both urls", () => {
    expect(historyUrl("p", "w", "a/b")).toBe("/api/oporahub/history/card/a%2Fb?project=p&workspace=w");
    expect(blameUrl("p", "w", "x")).toBe("/api/oporahub/blame/card/x?project=p&workspace=w");
  });
});
