import { describe, expect, it } from "vitest";
import { copyText } from "./use-copy-text";

describe("copyText", () => {
  it("zapíše text a hlásí úspěch", async () => {
    let written = "";
    expect(await copyText({ writeText: async (text) => { written = text; } }, "zadání")).toBe("copied");
    expect(written).toBe("zadání");
  });

  it("nedostupná schránka je neúspěch", async () => {
    expect(await copyText(undefined, "x")).toBe("failed");
    expect(await copyText({}, "x")).toBe("failed");
  });

  it("zamítnutí i synchronní výjimka jsou neúspěch, nic nevyhodí", async () => {
    expect(await copyText({ writeText: () => Promise.reject(new Error("denied")) }, "x")).toBe("failed");
    expect(await copyText({ writeText: () => { throw new Error("boom"); } }, "x")).toBe("failed");
  });
});
