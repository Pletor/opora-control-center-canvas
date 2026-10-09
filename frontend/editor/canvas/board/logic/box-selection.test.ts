import { describe, expect, it } from "vitest";
import { deletableSelection, isDeleteKey, reportsSelection, sameSelection, selectionIds, selectionPlan } from "./box-selection";

const key = (k: string, extra: Partial<{ ctrlKey: boolean; metaKey: boolean; altKey: boolean; shiftKey: boolean }> = {}) => ({
  key: k, ctrlKey: false, metaKey: false, altKey: false, shiftKey: false, ...extra,
});

describe("box-selection", () => {
  it("Delete i Backspace mažou, jiné klávesy ne", () => {
    expect(isDeleteKey(key("Delete"), null)).toBe(true);
    expect(isDeleteKey(key("Backspace"), null)).toBe(true);
    expect(isDeleteKey(key("Delete", { shiftKey: true }), null)).toBe(true);
    expect(isDeleteKey(key("d"), null)).toBe(false);
    expect(isDeleteKey(key("Escape"), null)).toBe(false);
  });

  it("s Ctrl, ⌘ nebo Alt klávesa nemaže", () => {
    expect(isDeleteKey(key("Backspace", { ctrlKey: true }), null)).toBe(false);
    expect(isDeleteKey(key("Delete", { metaKey: true }), null)).toBe(false);
    expect(isDeleteKey(key("Delete", { altKey: true }), null)).toBe(false);
  });

  it("při psaní do pole se nemaže na plátně", () => {
    expect(isDeleteKey(key("Backspace"), { tagName: "input" })).toBe(false);
    expect(isDeleteKey(key("Delete"), { tagName: "TEXTAREA" })).toBe(false);
    expect(isDeleteKey(key("Delete"), { tagName: "DIV", isContentEditable: true })).toBe(false);
    expect(isDeleteKey(key("Delete"), { tagName: "DIV" })).toBe(true);
  });

  it("výběr bere jen vybrané uzly grafu, boční bloky vynechá", () => {
    expect(
      selectionIds([
        { id: "a", selected: true },
        { id: "b", selected: false },
        { id: "block:action:a", selected: true },
        { id: "c", selected: true },
        { id: "d" },
      ]),
    ).toEqual(["a", "c"]);
  });

  it("smaže hromadný výběr, jinak jediný vybraný uzel", () => {
    const present = new Set(["a", "b", "c"]);
    expect(deletableSelection(["a", "b"], "c", present)).toEqual(["a", "b"]);
    expect(deletableSelection([], "c", present)).toEqual(["c"]);
    expect(deletableSelection([], null, present)).toEqual([]);
  });

  it("nesmaže, co na plátně není, ani boční blok, a každé id jen jednou", () => {
    const present = new Set(["a", "block:rule:a"]);
    expect(deletableSelection(["a", "a", "x", "block:rule:a"], null, present)).toEqual(["a"]);
    expect(deletableSelection([], "x", present)).toEqual([]);
  });

  it("stejný výběr nezávisí na pořadí", () => {
    expect(sameSelection(["a", "b"], ["b", "a"])).toBe(true);
    expect(sameSelection(["a"], ["a", "b"])).toBe(false);
    expect(sameSelection([], [])).toBe(true);
  });

  it("výběr se hlásí jen po změně výběru a ne po kliku na boční blok", () => {
    expect(reportsSelection([{ type: "position", id: "a" }])).toBe(false);
    expect(reportsSelection([{ type: "select", id: "a", selected: true }])).toBe(true);
    expect(reportsSelection([{ type: "select", id: "a", selected: false }])).toBe(true);
    expect(
      reportsSelection([
        { type: "select", id: "a", selected: false },
        { type: "select", id: "block:action:a", selected: true },
      ]),
    ).toBe(false);
  });

  it("dvě a víc položek je hromadný výběr, jedna obyčejný výběr uzlu", () => {
    expect(selectionPlan(["a", "b"])).toEqual({ multi: ["a", "b"], single: null });
    expect(selectionPlan(["a"])).toEqual({ multi: [], single: "a" });
    expect(selectionPlan([])).toEqual({ multi: [], single: null });
  });
});
