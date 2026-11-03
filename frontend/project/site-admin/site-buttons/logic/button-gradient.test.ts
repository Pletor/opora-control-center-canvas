import { expect, it } from "vitest";
import { addStop, backgroundCss, MAX_STOPS, removeStop, toggleGradient, withAngle, withStop } from "./button-gradient";
import type { Gradient } from "./button-model";

it("turns a color into a gradient from that color and back", () => {
  const gradient = toggleGradient("#1c9749", true) as Gradient;
  expect(gradient.gradient.stops[0]).toEqual({ color: "#1c9749", position: 0 });
  expect(gradient.gradient.stops).toHaveLength(2);
  expect(toggleGradient(gradient, false)).toBe("#1c9749");
});

it("edits angle and stops within the server limits", () => {
  let gradient = toggleGradient("#000000", true) as Gradient;
  gradient = withAngle(gradient, 400);
  expect(gradient.gradient.angle).toBe(360);
  gradient = withStop(gradient, 1, { position: 1.5, color: "{brand}" });
  expect(gradient.gradient.stops[1]).toEqual({ color: "{brand}", position: 1 });
  gradient = addStop(gradient);
  expect(gradient.gradient.stops.map((stop) => stop.position)).toEqual([0, 0.5, 1]);
  expect(removeStop(removeStop(gradient, 1), 0).gradient.stops).toHaveLength(2);
});

it("stops adding after eight stops", () => {
  let gradient = toggleGradient("#000000", true) as Gradient;
  for (let index = 0; index < 10; index++) gradient = addStop(gradient);
  expect(gradient.gradient.stops.length).toBe(MAX_STOPS);
});

it("writes the background like the server does", () => {
  const gradient: Gradient = { gradient: { angle: 90, stops: [{ color: "#000000", position: 0 }, { color: "{brand}", position: 0.25 }] } };
  expect(backgroundCss(gradient)).toBe("linear-gradient(90deg, #000000 0%, var(--brand) 25%)");
  expect(backgroundCss("#ffffff")).toBe("#ffffff");
  expect(backgroundCss(undefined)).toBeNull();
});
