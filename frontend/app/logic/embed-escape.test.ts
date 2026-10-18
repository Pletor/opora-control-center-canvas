import { describe, expect, it } from "vitest";
import { installEmbedEscape, parentOriginFrom, shouldForwardEscape, type EmbedWindow } from "./embed-escape";

function fakeWindow(framed: boolean) {
  const sent: Array<[unknown, string]> = [];
  const listeners: Array<(event: { key: string; defaultPrevented: boolean; isComposing?: boolean }) => void> = [];
  const self = {};
  const win: EmbedWindow = {
    self,
    top: framed ? {} : self,
    parent: { postMessage: (message, origin) => { sent.push([message, origin]); } },
    addEventListener: (_type, listener) => { listeners.push(listener); },
  };
  const press = (key: string, defaultPrevented = false, isComposing = false) =>
    listeners.forEach((listener) => listener({ key, defaultPrevented, isComposing }));
  return { win, sent, listeners, press };
}

describe("embed-escape", () => {
  it("původ rodiče bere jen z HTTP(S) referreru", () => {
    expect(parentOriginFrom("http://localhost:4600/office?x=1")).toBe("http://localhost:4600");
    expect(parentOriginFrom("")).toBeNull();
    expect(parentOriginFrom("nesmysl")).toBeNull();
    expect(parentOriginFrom("file:///c:/x.html")).toBeNull();
  });

  it("předá jen Escape, který Opora sama neobsloužila", () => {
    expect(shouldForwardEscape({ key: "Escape", defaultPrevented: false })).toBe(true);
    expect(shouldForwardEscape({ key: "Escape", defaultPrevented: true })).toBe(false);
    expect(shouldForwardEscape({ key: "Escape", defaultPrevented: false, isComposing: true })).toBe(false);
    expect(shouldForwardEscape({ key: "Enter", defaultPrevented: false })).toBe(false);
  });

  it("v rámu pošle rodiči zprávu jen na jeho původ", () => {
    const { win, sent, press } = fakeWindow(true);
    expect(installEmbedEscape(win, "http://localhost:4600/")).toBe(true);
    press("Escape");
    press("Escape", true);
    press("a");
    expect(sent).toEqual([[{ type: "opora:escape" }, "http://localhost:4600"]]);
  });

  it("mimo rám nebo bez referreru nic nezapojí", () => {
    const top = fakeWindow(false);
    expect(installEmbedEscape(top.win, "http://localhost:4600/")).toBe(false);
    const noReferrer = fakeWindow(true);
    expect(installEmbedEscape(noReferrer.win, "")).toBe(false);
    expect(top.listeners.length + noReferrer.listeners.length).toBe(0);
  });
});
