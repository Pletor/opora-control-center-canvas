import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import CardProcess from "./CardProcess";
import type { CardProcessView, ProcessDot } from "../logic/card-process";
import { proofSlots } from "../logic/card-proofs";

const dot = (id: string, over: Partial<ProcessDot> = {}): ProcessDot => ({
  id, kind: "work", lens: "", status: "todo", current: false, stuck: false, retry: false, title: id, note: "", doneBy: "", ...over,
});
const view = (dots: ProcessDot[], over: Partial<CardProcessView> = {}): CardProcessView => ({
  routed: dots.length > 0, profile: "code", profileLabel: "Kód", dots, finished: 1, total: dots.length, waitingOnHuman: false, proposed: 0,
  proofs: proofSlots(undefined, [], undefined), ...over,
});
const render = (v: CardProcessView, detail: "full" | "far" = "full") =>
  renderToStaticMarkup(createElement(CardProcess, { view: v, detail }));

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
  expect(html).toContain(">Kód<");
});

it("always draws the four proof slots in order, with labels only when near", () => {
  const near = render(view([dot("w")]));
  expect(near.match(/class="node-card__proof node-card__proof-/g)?.length).toBe(4);
  expect(near.indexOf("node-card__proof--tests")).toBeLessThan(near.indexOf("node-card__proof--security"));
  expect(near.indexOf("node-card__proof--security")).toBeLessThan(near.indexOf("node-card__proof--review"));
  expect(near.indexOf("node-card__proof--review")).toBeLessThan(near.indexOf("node-card__proof--merge"));
  expect(near).toContain(">Testy<");
  expect(near).toContain('title="Security · nedoloženo · kritik hacker zatím neproběhl"');
  const far = render(view([dot("w")]), "far");
  expect(far.match(/node-card__proof-box/g)?.length).toBe(4);
  expect(far).not.toContain("node-card__proof-label");
});

it("marks the security profile and hides the chip and count when far", () => {
  expect(render(view([dot("w")], { profile: "security", profileLabel: "Security" }))).toContain("node-card__process-profile--security");
  const far = render(view([dot("w")]), "far");
  expect(far).toContain("node-card__process--far");
  expect(far).not.toContain("node-card__process-profile");
  expect(far).not.toContain("node-card__process-count");
});

it("shows an unrouted node as waiting for the router, still with its proof slots", () => {
  const html = render(view([], { routed: false }));
  expect(html).toContain("node-card__process--unrouted");
  expect(html).toContain("čeká na router");
  expect(html.match(/node-card__proof-box/g)?.length).toBe(4);
});

it("hides dots from screen readers behind one sentence with the proofs", () => {
  const html = render(view([dot("w", { status: "passed" }), dot("c", { kind: "critic", lens: "hacker", current: true })], { proposed: 2 }));
  expect(html).toContain('class="node-card__process-dots" aria-hidden="true"');
  expect(html).toContain('<span class="node-card__process-sr">Proces: 1/2, na řadě Kritik: hacker, 2 ke schválení. Doklady: Testy nedoloženo, Security nedoloženo, Review nedoloženo, Merge nedoloženo</span>');
  expect(html).not.toContain("+2 ke schválení");
});
