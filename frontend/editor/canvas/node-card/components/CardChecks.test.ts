import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import CardChecks from "./CardChecks";
import ChecksEditor from "@/editor/node-detail/card-fields/components/ChecksEditor";
import type { CompletionEvidence } from "./CardEvidence";
import type { CanvasNode } from "@/shared/types/logic/types";

describe("structured checks", () => {
  it("shows success, failure and missing current command separately", () => {
    const evidence = { checksRun: [
      { checkId: "unit", command: "pytest", exitCode: 0, at: "2026-10-07T12:00:00Z", logUrl: "https://ci.example/log" },
      { checkId: "lint", command: "ruff check", exitCode: 1, at: "2026-10-07T12:00:00Z", logUrl: "https://ci.example/log" },
      { checkId: "old", command: "previous", exitCode: 0, at: "2026-10-07T12:00:00Z", logUrl: "https://ci.example/log" },
    ] } as CompletionEvidence;
    const html = renderToStaticMarkup(createElement(CardChecks, { checks: [
      { id: "unit", command: "pytest" }, { id: "lint", command: "ruff check" }, { id: "old", command: "current" },
    ], goal_mode: "until_checks_pass", evidence }));
    expect(html).toContain("✓ unit"); expect(html).toContain("✗ lint"); expect(html).toContain("… old"); expect(html).toContain("GOAL");
  });
  it("renders stored commands and read-only editor without executing them", () => {
    const node = { id: "n", kind: "node", name: "Task", checks: [{ id: "unit", command: "uv run pytest" }], goal_mode: "until_checks_pass" } as CanvasNode;
    const html = renderToStaticMarkup(createElement(ChecksEditor, { node, disabled: true, onSave: () => { throw Error("must not save"); } }));
    expect(html).toContain("uv run pytest"); expect(html).toContain("disabled"); expect(html).toContain("Příkazy se uložením nespouštějí");
  });
});
