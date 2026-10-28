import { describe, expect, it } from "vitest";
import { autonomyReadUrl, autonomyTitle, autonomyWriteBody, readAutonomy, sinceLabel } from "./agent-autonomy";

describe("readAutonomy – stav z odpovědi nastavení projektu", () => {
  it("zapnutá autonomie nese since a by", () => {
    expect(readAutonomy({ revision: 3, agentAutonomy: { full: true, since: "2026-10-28T10:00:00Z", by: "Martin" } }))
      .toEqual({ full: true, since: "2026-10-28T10:00:00Z", by: "Martin" });
  });
  it.each([
    ["bez pole (starý server)", { revision: 1 }],
    ["null", null],
    ["full není true", { agentAutonomy: { full: "true" } }],
    ["pole není objekt", { agentAutonomy: true }],
  ])("%s = vypnuto", (_, response) => {
    expect(readAutonomy(response)).toEqual({ full: false });
  });
  it("prázdné since a by se zahodí", () => {
    expect(readAutonomy({ agentAutonomy: { full: false, since: "", by: "" } })).toEqual({ full: false });
  });
});

describe("cesty a tělo zápisu", () => {
  it("čtení nese projekt v dotazu", () => {
    expect(autonomyReadUrl("a b")).toBe("/api/project-settings?project=a+b");
  });
  it("zápis nese projekt a full", () => {
    expect(autonomyWriteBody("p", true)).toEqual({ project: "p", full: true });
  });
});

describe("sinceLabel a autonomyTitle", () => {
  it("neplatný nebo chybějící čas = prázdný", () => {
    expect(sinceLabel(undefined)).toBe("");
    expect(sinceLabel("nesmysl")).toBe("");
  });
  it("čas česky v místním čase", () => {
    const at = new Date(2026, 9, 28, 14, 5).toISOString();
    expect(sinceLabel(at)).toBe("28. 10. 2026 14:05");
  });
  it("tooltip vysvětlí výjimky a řekne, kdo a kdy zapnul", () => {
    const at = new Date(2026, 9, 28, 9, 7).toISOString();
    const title = autonomyTitle({ full: true, since: at, by: "Martin" });
    expect(title).toContain("kromě přístupu");
    expect(title).toContain("Zapnuto 28. 10. 2026 09:07 (Martin).");
  });
  it("bez času, jen s autorem", () => {
    expect(autonomyTitle({ full: true, by: "Eva" })).toContain("Zapnul(a) Eva.");
  });
});
