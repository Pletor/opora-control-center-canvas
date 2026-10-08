import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import CardScenario from "./CardScenario";
import { setUrlDownload } from "../logic/input-security";
import type { DesktopState } from "@/shared/desktop-state/logic/types";

it("shows E2E totals, failure and trend, but does not approve an old command", () => {
  const run = { command: "e2e", at: "2026-10-07T12:00:00Z", passed: 30, failed: 1, logUrl: "https://ci.example/log", firstFailure: "Isolation" };
  const history = { latest: run, previous: { ...run, passed: 29, failed: 2 }, current: true, comparable: true, deltaPassed: 1, deltaFailed: -1 };
  const html = renderToStaticMarkup(createElement(CardScenario, { command: "e2e", history }));
  expect(html).toContain("30/31 ✗"); expect(html).toContain("Isolation"); expect(html).toContain("↗"); expect(html).toContain("FAIL -1");
  const stale = renderToStaticMarkup(createElement(CardScenario, { command: "new", history: { ...history, current: false, comparable: false } }));
  expect(stale).toContain("starý příkaz"); expect(stale).not.toContain("✓");
});

it("adds the required security block once and preserves it when toggled off", () => {
  const state = { settings: [], rules: [], decisions: [], tickets: [], nodes: {}, edges: {} } as DesktopState;
  const once = setUrlDownload("n", true)(state);
  const twice = setUrlDownload("n", true)(once);
  expect(twice.nodes.n.blocks).toHaveLength(1);
  expect(twice.nodes.n.blocks![0].tags).toContain("input-security");
  expect(twice.nodes.n.blocks![0].state.condition).toContain("SSRF");
  expect(setUrlDownload("n", false)(twice).nodes.n.blocks).toEqual(twice.nodes.n.blocks);
});
