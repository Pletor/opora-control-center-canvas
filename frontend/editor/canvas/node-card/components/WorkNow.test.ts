import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import WorkNow, { WorkDetails } from "./WorkNow";
import type { WorkRow } from "../logic/use-work-overview";

const row: WorkRow = { id: "n", name: "Task", status: "claimed", agent: "worker", startedAt: "2026-10-07T12:00:00Z", lastActivity: "2026-10-07T12:01:00Z", touched: ["src/one.py"], waitingOnHuman: [], blockedBy: [] };
it("shows current work, files and sector totals", () => {
  const html = renderToStaticMarkup(createElement(WorkNow, { sectorId: "s", open: () => {}, overview: { nodes: { n: row }, sectors: { s: { waiting: 11, claimed: 2, "waiting-human": 0, proposed: 1, done: 3, blocked: 0 } } } }));
  expect(html).toContain("Teď se děje"); expect(html).toContain("worker"); expect(html).toContain("@src/one.py");
  expect(html).toContain("3 hotovo"); expect(html).toContain("1 ke schválení"); expect(html).toContain("Poslední aktivita");
});
it("distinguishes unknown files from an explicitly empty list", () => {
  expect(renderToStaticMarkup(createElement(WorkDetails, { row: { ...row, touched: null } }))).toContain("nedoloženy");
  expect(renderToStaticMarkup(createElement(WorkDetails, { row: { ...row, touched: [] } }))).toContain("bez změněných souborů");
});
