import { describe, expect, it } from "vitest";
import { isTypingTarget, undoIntent, type ShortcutKey } from "./undo-shortcut";

function key(value: string, modifiers: Partial<ShortcutKey> = {}): ShortcutKey {
  return { key: value, ctrlKey: false, metaKey: false, shiftKey: false, altKey: false, ...modifiers };
}

describe("undo-shortcut", () => {
  it("Ctrl+Z i ⌘Z vrací krok zpět", () => {
    expect(undoIntent(key("z", { ctrlKey: true }))).toBe("undo");
    expect(undoIntent(key("Z", { metaKey: true }))).toBe("undo");
  });

  it("Ctrl+Shift+Z a Ctrl+Y vedou krok vpřed", () => {
    expect(undoIntent(key("z", { ctrlKey: true, shiftKey: true }))).toBe("redo");
    expect(undoIntent(key("y", { ctrlKey: true }))).toBe("redo");
    expect(undoIntent(key("Z", { metaKey: true, shiftKey: true }))).toBe("redo");
  });

  it("bez modifikátoru, s Altem nebo s jinou klávesou se nic nechytá", () => {
    expect(undoIntent(key("z"))).toBeNull();
    expect(undoIntent(key("z", { ctrlKey: true, altKey: true }))).toBeNull();
    expect(undoIntent(key("y", { ctrlKey: true, shiftKey: true }))).toBeNull();
    expect(undoIntent(key("s", { ctrlKey: true }))).toBeNull();
    expect(undoIntent(key("1", { altKey: true }))).toBeNull();
  });

  it("psaní do pole, textarea, výběru a editovatelného textu si zkratku nechává", () => {
    expect(isTypingTarget({ tagName: "INPUT" })).toBe(true);
    expect(isTypingTarget({ tagName: "textarea" })).toBe(true);
    expect(isTypingTarget({ tagName: "SELECT" })).toBe(true);
    expect(isTypingTarget({ tagName: "DIV", isContentEditable: true })).toBe(true);
  });

  it("prvek uvnitř data-no-undo je pro historii neviditelný", () => {
    const inside = { tagName: "SPAN", closest: (selector: string) => (selector.includes("data-no-undo") ? {} : null) };
    expect(isTypingTarget(inside)).toBe(true);
  });

  it("obyčejné plátno zkratku pustí dál", () => {
    expect(isTypingTarget({ tagName: "DIV", closest: () => null })).toBe(false);
    expect(isTypingTarget(null)).toBe(false);
    expect(isTypingTarget(undefined)).toBe(false);
  });
});
