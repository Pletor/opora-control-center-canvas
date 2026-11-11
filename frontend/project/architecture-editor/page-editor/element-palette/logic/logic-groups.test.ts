import { describe, expect, it } from "vitest";
import { LOGIC_GROUPS, logicLook } from "./logic-groups";

describe("paleta logiky", () => {
  it("šest otázek a každý druh jen jednou", () => {
    expect(LOGIC_GROUPS.map((group) => group.question)).toEqual(["Kdo", "Kdo smí", "Co musí splnit", "Co se děje", "S čím", "Napojení"]);
    const kinds = LOGIC_GROUPS.flatMap((group) => group.kinds.map((item) => item.kind));
    expect(new Set(kinds).size).toBe(kinds.length);
  });
  it("štítek nese popisek plátna 2, druh mimo paletu popisek Editoru", () => {
    expect(logicLook("actor")).toEqual({ label: "Uživatel", icon: "user" });
    expect(logicLook("permission")).toEqual({ label: "Přístup", icon: "security" });
    expect(logicLook("dialog")).toEqual({ label: "Dialog", icon: "logic" });
  });
});
