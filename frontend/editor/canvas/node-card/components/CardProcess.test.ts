import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import CardProcess from "./CardProcess";
import type { CardProcessView, ProcessDot } from "../logic/card-process";

const dot = (id: string, over: Partial<ProcessDot> = {}): ProcessDot => ({
  id, kind: "work", lens: "", status: "todo", current: false, stuck: false, retry: false, title: id, note: "", doneBy: "", ...over,
});
const view = (dots: ProcessDot[], over: Partial<CardProcessView> = {}): CardProcessView => ({
  routed: dots.length > 0, profile: "code", profileLabel: "Kód", dots, finished: 1, total: dots.length, waitingOnHuman: false, proposed: 0, ...over,
});
const render = (v: CardProcessView, detail: "full" | "far" = "full", kind: "node" | "sector" = "node") =>
  renderToStaticMarkup(createElement(CardProcess, { view: v, detail, kind }));

it("draws one dot per stage with kind, lens and status classes", () => {
  const html = render(view([
    dot("w", { status: "passed" }),
    dot("c", { kind: "critic", lens: "hacker", status: "failed", stuck: true }),
    dot("r", { kind: "review", current: true }),
  ], { waitingOnHuman: true }));
  expect(html.match(/class="node-card__stage /g)?.length).toBe(3);
  expect(html).toContain("node-card__stage--status-passed");
  expect(html).toContain("node-card__stage--lens-hacker");
  expect(html).toContain("node-card__stage--stuck");
  expect(html).toContain("node-card__stage--current");
  expect(html).toContain("1/3");
  expect(html).toContain("👤 čeká");
  expect(html).toContain(">Kód<");
});

it("marks the security profile and hides the chip and count when far", () => {
  expect(render(view([dot("w")], { profile: "security", profileLabel: "Security" }))).toContain("node-card__process-profile--security");
  const far = render(view([dot("w")]), "far");
  expect(far).toContain("node-card__process--far");
  expect(far).not.toContain("node-card__process-profile");
  expect(far).not.toContain("node-card__process-count");
});

it("shows an unrouted node as waiting for the router and draws nothing for a sector", () => {
  const html = render(view([], { routed: false }));
  expect(html).toContain("node-card__process--unrouted");
  expect(html).toContain("čeká na router");
  expect(render(view([], { routed: false }), "full", "sector")).toBe("");
});

it("hides dots from screen readers behind one sentence and shows pending proposals", () => {
  const html = render(view([dot("w", { status: "passed" }), dot("c", { kind: "critic", lens: "hacker", current: true })], { proposed: 2 }));
  expect(html).toContain('class="node-card__process-dots" aria-hidden="true"');
  expect(html).toContain('<span class="node-card__process-sr">Proces: 1/2, na řadě Kritik: hacker, 2 ke schválení</span>');
  expect(html).toContain("+2 ke schválení");
  expect(render(view([dot("w")], { proposed: 2 }), "far")).not.toContain("node-card__process-proposed");
});
