import { describe, expect, it } from "vitest";
import { fileIdOf } from "./sketch-files";

describe("fileIdOf", () => {
  it("dává stabilní SHA-1 hex, který projde pravidlem backendu pro fileId", async () => {
    const id = await fileIdOf("data:image/png;base64,AAAA");
    expect(id).toMatch(/^[a-f0-9]{40}$/);
    expect(await fileIdOf("data:image/png;base64,AAAA")).toBe(id);
    expect(await fileIdOf("data:image/png;base64,BBBB")).not.toBe(id);
  });
});
