import { describe, expect, it } from "vitest";
import { isExternalTaskPath } from "@/shared/desktop-state/logic/api";

describe("external task export path", () => {
  it("accepts the canvas data path on Windows and POSIX", () => {
    expect(isExternalTaskPath("C:\\data\\projects\\p1\\packets\\external-tasks\\w1\\n1.md", "w1", "n1")).toBe(true);
    expect(isExternalTaskPath("/data/projects/p1/packets/external-tasks/w1/n1.md", "w1", "n1")).toBe(true);
  });

  it("rejects the old repository path and foreign scope", () => {
    expect(isExternalTaskPath("docs/opora-control-center/tasks/n1.md", "w1", "n1")).toBe(false);
    expect(isExternalTaskPath("/data/projects/p1/packets/external-tasks/w2/n1.md", "w1", "n1")).toBe(false);
    expect(isExternalTaskPath(undefined, "w1", "n1")).toBe(false);
  });
});
