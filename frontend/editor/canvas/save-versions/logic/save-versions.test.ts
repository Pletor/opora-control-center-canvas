import { describe, expect, it } from "vitest";
import {
  LOCAL_AUTHOR,
  authorLine,
  canRestore,
  headChanged,
  clockLabel,
  isSaveShortcut,
  relativeTime,
  saveButtonView,
  versionAuthor,
  versionLabel,
  withSavedVersion,
  type CanvasVersion,
} from "./save-versions";
import type { Workspace } from "@/shared/types/logic/types";

const now = new Date(2026, 9, 5, 12, 0, 0);
const ago = (ms: number) => new Date(now.getTime() - ms);
const MIN = 60_000;
const HOUR = 60 * MIN;
const DAY = 24 * HOUR;

describe("relativeTime", () => {
  it("do minuty a v budoucnu je to Právě teď", () => {
    expect(relativeTime(ago(0), now)).toBe("Právě teď");
    expect(relativeTime(ago(59_000), now)).toBe("Právě teď");
    expect(relativeTime(ago(-5 * MIN), now)).toBe("Právě teď");
    expect(relativeTime("nesmysl", now)).toBe("Právě teď");
  });

  it("skloňuje minuty a hodiny", () => {
    expect(relativeTime(ago(MIN), now)).toBe("Před 1 minutou");
    expect(relativeTime(ago(2 * MIN), now)).toBe("Před 2 minutami");
    expect(relativeTime(ago(5 * MIN), now)).toBe("Před 5 minutami");
    expect(relativeTime(ago(HOUR), now)).toBe("Před 1 hodinou");
    expect(relativeTime(ago(3 * HOUR), now)).toBe("Před 3 hodinami");
  });

  it("skloňuje dny, měsíce a roky", () => {
    expect(relativeTime(ago(DAY), now)).toBe("Před 1 dnem");
    expect(relativeTime(ago(4 * DAY), now)).toBe("Před 4 dny");
    expect(relativeTime(ago(31 * DAY), now)).toBe("Před 1 měsícem");
    expect(relativeTime(ago(95 * DAY), now)).toBe("Před 3 měsíci");
    expect(relativeTime(ago(364 * DAY), now)).toBe("Před 11 měsíci");
    expect(relativeTime(ago(366 * DAY), now)).toBe("Před 1 rokem");
    expect(relativeTime(ago(800 * DAY), now)).toBe("Před 2 roky");
  });
});

describe("clockLabel a versionLabel", () => {
  it("formát d. m. HH:MM v místním čase", () => {
    expect(clockLabel(new Date(2026, 6, 21, 12, 32))).toBe("21. 7. 12:32");
    expect(clockLabel(new Date(2026, 0, 3, 8, 5))).toBe("3. 1. 08:05");
    expect(clockLabel("nesmysl")).toBe("");
  });

  it("řádek verze spojí relativní čas a hodiny", () => {
    const july = new Date(2026, 6, 21, 12, 32);
    expect(versionLabel(july, new Date(2026, 9, 21, 12, 32))).toBe("Před 3 měsíci (21. 7. 12:32)");
  });
});

describe("autor", () => {
  const ws = (id: string, actor: string) => ({ id, actor }) as Workspace;

  it("bere vlastníka otevřeného prostoru, jinak místního uživatele", () => {
    expect(versionAuthor([ws("w1", " Martin ")], "w1")).toBe("Martin");
    expect(versionAuthor([ws("w1", "Martin")], "main")).toBe(LOCAL_AUTHOR);
    expect(versionAuthor([ws("w1", "  ")], "w1")).toBe(LOCAL_AUTHOR);
    expect(versionAuthor(undefined, "w1")).toBe(LOCAL_AUTHOR);
    expect(versionAuthor([ws("w1", "x".repeat(200))], "w1")).toHaveLength(120);
  });

  it("řádek autora", () => {
    expect(authorLine("Martin")).toBe("Autor: Martin");
    expect(authorLine("")).toBe(`Autor: ${LOCAL_AUTHOR}`);
  });
});

describe("tlačítko ULOŽIT", () => {
  it("klid, neuloženo a ukládání", () => {
    expect(saveButtonView(false, false)).toMatchObject({ label: "ULOŽIT", dirty: false });
    expect(saveButtonView(true, false)).toEqual({ label: "ULOŽIT", title: "Změny nejsou uložené ve verzi", dirty: true });
    expect(saveButtonView(true, true).label).toBe("Ukládám…");
  });
});

describe("seznam verzí", () => {
  const v = (id: string): CanvasVersion => ({ id, createdAt: now.toISOString(), author: "A", nodeCount: 1 });

  it("uložená verze jde nahoru a neopakuje se", () => {
    expect(withSavedVersion([v("a"), v("b")], v("c")).map((x) => x.id)).toEqual(["c", "a", "b"]);
    expect(withSavedVersion([v("a"), v("b")], v("b")).map((x) => x.id)).toEqual(["b", "a"]);
  });

  it("obnovit jde jen vybranou verzi ze seznamu", () => {
    expect(canRestore([v("a")], "a")).toBe(true);
    expect(canRestore([v("a")], "z")).toBe(false);
    expect(canRestore([v("a")], null)).toBe(false);
  });
});

describe("isSaveShortcut", () => {
  const key = (k: string, mods: Partial<{ ctrlKey: boolean; metaKey: boolean; shiftKey: boolean; altKey: boolean }> = {}) =>
    ({ key: k, ctrlKey: false, metaKey: false, shiftKey: false, altKey: false, ...mods });

  it("Ctrl+S i ⌘S, ne samotné S ani s Altem / Shiftem", () => {
    expect(isSaveShortcut(key("s", { ctrlKey: true }))).toBe(true);
    expect(isSaveShortcut(key("S", { metaKey: true }))).toBe(true);
    expect(isSaveShortcut(key("s"))).toBe(false);
    expect(isSaveShortcut(key("s", { ctrlKey: true, altKey: true }))).toBe(false);
    expect(isSaveShortcut(key("s", { ctrlKey: true, shiftKey: true }))).toBe(false);
    expect(isSaveShortcut(key("z", { ctrlKey: true }))).toBe(false);
  });
});

describe("headChanged", () => {
  it("downloads the version list only when the cheap head shows other content or dirty flag", () => {
    const seen = { currentToken: "t1", dirty: false };
    expect(headChanged(null, seen)).toBe(true);
    expect(headChanged(seen, { currentToken: "t1", dirty: false })).toBe(false);
    expect(headChanged(seen, { currentToken: "t2", dirty: false })).toBe(true);
    expect(headChanged(seen, { currentToken: "t1", dirty: true })).toBe(true);
  });
});
