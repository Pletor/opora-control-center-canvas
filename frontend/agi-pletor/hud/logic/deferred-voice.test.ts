import { describe, expect, it } from "vitest";
import { createDeferredVoice } from "./deferred-voice";
import type { PletorMessage } from "./pletor-client";
const message = (role: PletorMessage["role"], text: string, at: string): PletorMessage => ({ role, text, at });

describe("deferred voice", () => {
  it("keeps announcements through thinking pauses and reads all once after release", () => {
    const queue = createDeferredVoice();
    const history = [message("human", "Otázka", "1"), message("pletor", "Prověřím", "2")];
    queue.observe(history, true); expect(queue.next(false)).toBeUndefined();
    const updated = [...history, message("heart", "Výsledek", "3"), message("pletor", "První zpráva", "4"), message("pletor", "Druhá zpráva", "5")];
    queue.observe(updated, true);
    expect(queue.next(true)).toBeUndefined(); expect(queue.next(true)).toBeUndefined();
    queue.observe(updated, true);
    expect(queue.next(false)?.text).toBe("První zpráva");
    expect(queue.next(false)?.text).toBe("Druhá zpráva");
    expect(queue.next(false)).toBeUndefined();
  });
  it("does not misclassify direct replies and discards old scope on reload", () => {
    const queue = createDeferredVoice(); queue.observe([], true);
    queue.observe([message("human", "dotaz", "1"), message("pletor", "odpověď", "2")], true);
    expect(queue.next(false)).toBeUndefined();
    queue.add({ text: "odložená hlasová odpověď", spoken: true });
    expect(queue.next(true)).toBeUndefined();
    queue.observe([], false); queue.observe([message("pletor", "jiná historie", "3")], true);
    expect(queue.next(false)).toBeUndefined();
  });
});
