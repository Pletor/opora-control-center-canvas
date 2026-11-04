import { describe, expect, it } from "vitest";
import { fileProblem, fileSize, groupNameProblem, newGroupName, renameGroup, withFile, withoutFile } from "./assets";

const file = (name: string, size = 10) => ({ name, blob: `assets/Logos/${name}`, size, type: "image/svg+xml" });
const groups = [{ name: "Logos", readme: "", files: [file("mark.svg")] }, { name: "New set", readme: "", files: [] }];

describe("skupiny assetů", () => {
  it("nová skupina má volné jméno a jméno má gramatiku serveru", () => {
    expect(newGroupName([])).toBe("New set");
    expect(newGroupName(groups)).toBe("New set 2");
    expect(groupNameProblem("Icons", groups)).toBe("");
    expect(groupNameProblem("Logos", groups)).toMatch(/existuje/);
    expect(groupNameProblem("Logos", groups, "Logos")).toBe("");
    expect(groupNameProblem("bad.", groups)).toMatch(/Jméno skupiny/);
  });

  it("soubor: přípona, jméno a velikost jako server", () => {
    expect(fileProblem({ name: "mark.svg", size: 10 })).toBe("");
    expect(fileProblem({ name: "run.exe", size: 10 })).toMatch(/typ/);
    expect(fileProblem({ name: "big.svg", size: 3 * 1024 * 1024 })).toMatch(/2 MB/);
    expect(fileProblem({ name: "big.png", size: 3 * 1024 * 1024 })).toBe("");
    expect(fileProblem({ name: "empty.png", size: 0 })).toMatch(/prázdný/);
  });

  it("nahraný soubor stejného jména přepíše, odebrání a přejmenování jen prázdné skupiny", () => {
    const next = withFile(groups, "Logos", file("mark.svg", 99));
    expect(next[0].files).toEqual([file("mark.svg", 99)]);
    expect(withFile(groups, "Logos", file("wordmark.svg"))[0].files.map((one) => one.name)).toEqual(["mark.svg", "wordmark.svg"]);
    expect(withFile([], "Other", file("a.svg")).map((group) => [group.name, group.files.length])).toEqual([["Other", 1]]);
    expect(withoutFile(groups, "Logos", "mark.svg")[0].files).toEqual([]);
    expect(renameGroup(groups, "Logos", "Brand")[0].name).toBe("Logos");
    expect(renameGroup(groups, "New set", "Icons")[1].name).toBe("Icons");
    expect([fileSize(500), fileSize(2048), fileSize(3 * 1024 * 1024)]).toEqual(["500 B", "2.0 kB", "3.0 MB"]);
  });
});
