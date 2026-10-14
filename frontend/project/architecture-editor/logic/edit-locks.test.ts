import { describe, expect, it } from "vitest";
import { architectureEditable, contentLock, structureLock, type LockInput } from "./edit-locks";

const open: LockInput = {
  loaded: true, loadError: "", ready: true, busy: false, loading: false, removing: false, removalOpen: false, scopeError: "",
  architectureEditable: true, readOnly: false, desktopLoading: false, desktopError: "", desktopReadOnly: false, scopeClosed: false,
};

describe("edit locks", () => {
  it("leaves both open in a writable worktree", () => {
    expect(structureLock(open)).toBeNull();
    expect(contentLock(open)).toBeNull();
  });

  it("keeps structure open on Git main while content is read-only", () => {
    const main = { ...open, readOnly: true, desktopReadOnly: true };
    expect(structureLock(main)).toBeNull();
    expect(contentLock(main)?.text).toContain("jen pro čtení");
    expect(contentLock(main)?.transient).toBe(false);
  });

  it("explains a structure lock when the backend refuses architecture writes", () => {
    expect(structureLock({ ...open, architectureEditable: false })?.text).toContain("nelze upravovat");
  });

  it("marks saving and loading as transient", () => {
    expect(structureLock({ ...open, busy: true })).toEqual({ text: "Ukládám změnu…", transient: true });
    expect(structureLock({ ...open, loaded: false })?.transient).toBe(true);
    expect(contentLock({ ...open, desktopLoading: true })?.text).toBe("Načítám stav karet…");
  });

  it("says why when loading failed, the scope is invalid or the card is closed", () => {
    expect(structureLock({ ...open, loaded: false, loadError: "HTTP 500" })?.text).toContain("HTTP 500");
    expect(structureLock({ ...open, scopeError: "Doména neexistuje." })?.text).toContain("Doména neexistuje.");
    expect(structureLock({ ...open, scopeClosed: true })?.text).toContain("uzavřená");
    expect(structureLock({ ...open, desktopError: "x" })?.transient).toBe(false);
    expect(structureLock({ ...open, removalOpen: true })?.text).toContain("odstranění");
  });

  it("falls back to readOnly for an older view without the flag", () => {
    expect(architectureEditable(null)).toBe(false);
    expect(architectureEditable({ readOnly: true })).toBe(false);
    expect(architectureEditable({ readOnly: false })).toBe(true);
    expect(architectureEditable({ readOnly: true, architectureEditable: true })).toBe(true);
  });
});
