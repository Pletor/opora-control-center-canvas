import { describe, expect, it } from "vitest";
import { slashHints } from "./slash-commands";

describe("nápověda lomítkových příkazů", () => {
  it("samotné lomítko nabídne všechny příkazy", () => {
    expect(slashHints("/").map((c) => c.name)).toEqual(["/grill-me", "/wayfinder"]);
  });

  it("filtruje podle napsaného začátku", () => {
    expect(slashHints("/gr").map((c) => c.name)).toEqual(["/grill-me"]);
    expect(slashHints("/x")).toEqual([]);
  });

  it("zmizí po dopsání příkazu, mezeře nebo bez lomítka", () => {
    expect(slashHints("/grill-me")).toEqual([]);
    expect(slashHints("/grill-me plán")).toEqual([]);
    expect(slashHints("ahoj /")).toEqual([]);
  });
});
