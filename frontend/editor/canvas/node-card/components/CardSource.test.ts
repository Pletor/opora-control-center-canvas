import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import CardSource from "./CardSource";

it("distinguishes existing links from planned sources on the canvas", () => {
  const render = (origin: "existing" | "planned") => renderToStaticMarkup(createElement(CardSource, {
    project: "p", workspace: "draft", source: { origin, path: "backend/main.py", kind: "file" },
  }));
  expect(render("existing")).toContain("@backend/main.py");
  expect(render("existing")).toContain("Otevřít ve VS Code");
  expect(render("existing")).not.toContain('disabled=""');
  expect(render("planned")).toContain('disabled=""');
  expect(render("planned")).toContain("· plán");
});
