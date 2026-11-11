import { describe, expect, it } from "vitest";
import type { PageSection } from "@/shared/types/logic/types";
import { addInspirationFiles, boxSketchLayer, inspirationRejects, inspirationUrlError, patchLock, patchSection, removeInspirationFile, statusOf } from "./box-detail";

const sec = (id: string, extra: Partial<PageSection> = {}): PageSection => ({ id, role: "content", name: id, intent: "", ...extra });

describe("detail boxu", () => {
  it("stav chybí = Rozpracováno; vrstva skici", () => {
    expect(statusOf({})).toBe("draft");
    expect(statusOf({ status: "proposed" })).toBe("proposed");
    expect(boxSketchLayer("p1", "hero")).toBe("box/p1/hero");
  });
  it("patchSection změní jen jednu sekci a beze změny vrací týž seznam", () => {
    const list = [sec("a"), sec("b")];
    const next = patchSection(list, "b", { status: "approved" });
    expect(next[1]).toEqual(sec("b", { status: "approved" }));
    expect(next[0]).toBe(list[0]);
    expect(patchSection(list, "b", { name: "b" })).toBe(list);
    expect(patchSection(list, "x", { name: "y" })).toBe(list);
  });
  it("inspirace je obsah, ostatní struktura", () => {
    expect(patchLock({ inspiration: {} })).toBe("content");
    expect(patchLock({ status: "approved", name: "x" })).toBe("structure");
  });
  it("obrázek: typ, velikost a limit 6", () => {
    expect(inspirationRejects({ type: "image/png", size: 10 }, 0)).toBeNull();
    expect(inspirationRejects({ type: "image/svg+xml", size: 10 }, 0)).toMatch(/PNG/);
    expect(inspirationRejects({ type: "image/png", size: 11 * 1024 * 1024 }, 0)).toMatch(/10 MB/);
    expect(inspirationRejects({ type: "image/png", size: 10 }, 6)).toMatch(/6/);
  });
  it("přidání bez duplicit do limitu, odebrání", () => {
    expect(addInspirationFiles({ files: ["a"], url: "https://x.cz" }, ["a", "b"])).toEqual({ files: ["a", "b"], url: "https://x.cz" });
    expect(addInspirationFiles(undefined, ["1", "2", "3", "4", "5", "6", "7"]).files).toHaveLength(6);
    expect(removeInspirationFile({ files: ["a", "b"] }, "a")).toEqual({ files: ["b"] });
  });
  it("odkaz: prázdný nebo http(s)", () => {
    expect(inspirationUrlError(" ")).toBeNull();
    expect(inspirationUrlError("https://example.com/a")).toBeNull();
    expect(inspirationUrlError("javascript:alert(1)")).toMatch(/https/);
    expect(inspirationUrlError("není url")).toMatch(/platná/);
  });
});
