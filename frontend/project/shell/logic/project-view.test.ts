import { expect, it } from "vitest";
import { readProjectView } from "./project-view";

it("restores studio and intent links and sends heart, graphify, old or unknown project links to the architecture", () => {
  expect(readProjectView(new URLSearchParams("projectView=architecture&layer=page&node=page").get("projectView"))).toBe("architecture");
  expect(readProjectView("studio")).toBe("studio");
  expect(readProjectView("intent")).toBe("intent");
  expect(readProjectView("heart")).toBe("architecture");
  expect(readProjectView("graphify")).toBe("architecture");
  expect(readProjectView("archify")).toBe("architecture");
  expect(readProjectView(null)).toBe("architecture");
  expect(readProjectView("unknown")).toBe("architecture");
});
