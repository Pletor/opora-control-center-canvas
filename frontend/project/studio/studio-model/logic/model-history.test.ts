import { describe, expect, it } from "vitest";
import { commit, HISTORY_LIMIT, historyOf, redo, undo } from "./model-history";

describe("model history", () => {
  it("undoes and redoes steps and a new step drops the future", () => {
    let history = commit(commit(historyOf("a"), "b"), "c");
    history = undo(history);
    expect(history.present).toBe("b");
    expect(redo(history).present).toBe("c");
    history = commit(undo(history), "x");
    expect(history).toEqual({ past: ["a"], present: "x", future: [], mergeKey: null });
    expect(undo(historyOf("a")).present).toBe("a");
    expect(redo(historyOf("a")).present).toBe("a");
  });

  it("merges typing into one field and ignores an unchanged model", () => {
    let history = commit(historyOf("a"), "ab", "name:s");
    history = commit(history, "abc", "name:s");
    expect(history.past).toEqual(["a"]);
    expect(undo(history).present).toBe("a");
    expect(commit(history, "abc")).toBe(history);
    expect(commit(undo(history), "z", "name:s").past).toEqual(["a"]);
  });

  it("keeps at most the limit of steps", () => {
    let history = historyOf(0);
    for (let step = 1; step <= HISTORY_LIMIT + 5; step++) history = commit(history, step);
    expect(history.past.length).toBe(HISTORY_LIMIT);
    expect(history.past[0]).toBe(5);
  });
});
