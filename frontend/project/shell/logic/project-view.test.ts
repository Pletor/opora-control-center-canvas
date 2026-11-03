import { expect, it } from "vitest";
import { readProjectView } from "./project-view";

it("restores graphify, studio and heart links and sends old or unknown project links to the architecture", () => {
  expect(readProjectView(new URLSearchParams("projectView=architecture&layer=page&node=page").get("projectView"))).toBe("architecture");
  expect(readProjectView("graphify")).toBe("graphify");
  expect(readProjectView("studio")).toBe("studio");
  expect(readProjectView("heart")).toBe("heart");
  expect(readProjectView("intent")).toBe("intent");
  expect(readProjectView("archify")).toBe("architecture");
  expect(readProjectView(null)).toBe("architecture");
  expect(readProjectView("unknown")).toBe("architecture");
});
