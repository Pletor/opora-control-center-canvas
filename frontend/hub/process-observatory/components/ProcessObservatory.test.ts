import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import FlowMap from "../flow-map/components/FlowMap";
import EventStream from "../event-stream/components/EventStream";
import CardInspector from "../card-inspector/components/CardInspector";
import BlockersStrip from "./BlockersStrip";
import { buildLanes } from "../logic/lanes";
import { flow } from "../logic/fixtures";

const EMPTY = "Zatím žádná událost — kancelář ani Opora nic nehlásí";
const stream = (extra = {}) => renderToStaticMarkup(createElement(EventStream, { rows: [], total: 0, paused: false, buffered: 0, anyEvent: false,
  cards: [], workers: [], card: "", worker: "", onCard: vi.fn(), onWorker: vi.fn(), onTogglePause: vi.fn(), ...extra }));

describe("Živý proces parts", () => {
  it("says honestly that nothing came in, in the map and in the stream", () => {
    expect(renderToStaticMarkup(createElement(FlowMap, { lanes: [], selected: null, now: 0, onSelect: vi.fn(), officeSilence: null }))).toContain(EMPTY);
    expect(stream()).toContain(EMPTY);
    expect(renderToStaticMarkup(createElement(CardInspector, { lane: null, onOpenCard: vi.fn() }))).toContain("Vyberte řádek v mapě");
  });
  it("draws a row per card with the marker in its phase and blockers on top", () => {
    const lanes = buildLanes([], [flow(1, "a", "needs.input", "plan", "blocked"), flow(2, "b", "tool.use", "work", "progress")], { names: { a: "Paměť agenta" }, officeConnected: true });
    const map = renderToStaticMarkup(createElement(FlowMap, { lanes, selected: "a", now: Date.now(), onSelect: vi.fn(), officeSilence: "před 3 min" }));
    expect(map).toContain('data-oh-card="a" data-oh-phase="plan"');
    expect(map).toContain("flow-map__marker--blocked");
    expect(map).toContain("Kancelář odpojena před 3 min.");
    const blockers = renderToStaticMarkup(createElement(BlockersStrip, { lanes, now: Date.now(), onSelect: vi.fn() }));
    expect(blockers).toContain('data-oh-blocker="a"');
    expect(blockers).not.toContain('data-oh-blocker="b"');
  });
  it("shows the buffered counter while reading is paused", () => {
    const html = stream({ paused: true, buffered: 7, anyEvent: true, rows: [flow(1, "a", "x", "work", "ok")] });
    expect(html).toContain("Pokračovat ve čtení");
    expect(html).toContain("+7");
    expect(html).toContain("7 nových událostí");
  });
  it("offers the unified card drawer from the inspector", () => {
    const [lane] = buildLanes([], [flow(1, "a", "tool.use", "work", "progress")], { names: {}, officeConnected: true });
    expect(renderToStaticMarkup(createElement(CardInspector, { lane, onOpenCard: vi.fn() }))).toContain("Otevřít detail karty");
  });
});
