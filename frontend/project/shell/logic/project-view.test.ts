import { expect, it } from "vitest";
import { readProjectView } from "./project-view";

it("restores architecture links and keeps old project links on Archify", () => {
  expect(readProjectView(new URLSearchParams("projectView=architecture&layer=page&node=page").get("projectView"))).toBe("architecture");
  expect(readProjectView("graphify")).toBe("graphify");
  expect(readProjectView("archify")).toBe("archify");
  expect(readProjectView(null)).toBe("archify");
  expect(readProjectView("unknown")).toBe("archify");
});
