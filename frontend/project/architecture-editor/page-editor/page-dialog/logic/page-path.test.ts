import { describe, expect, it } from "vitest";
import { pathFromName } from "./page-path";

describe("adresa z názvu", () => {
  it("bez diakritiky, malými písmeny, znaky na pomlčky", () => {
    expect(pathFromName("Členská sekce – Kurz!")).toBe("/clenska-sekce-kurz");
    expect(pathFromName("  Úvod  ")).toBe("/uvod");
  });
  it("podstránka pod cestou rodiče, prázdný název nechá cestu rodiče", () => {
    expect(pathFromName("Platba", "/kurz/")).toBe("/kurz/platba");
    expect(pathFromName("", "/kurz")).toBe("/kurz");
    expect(pathFromName("???")).toBe("/");
  });
});
