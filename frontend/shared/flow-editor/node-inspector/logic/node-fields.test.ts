import { expect, it } from "vitest";
import { parseJsonField, parseRetry, pretty } from "./node-fields";

it("checks schema and example JSON before it reaches the graph", () => {
  expect(parseJsonField('{"type":"object"}', true)).toEqual({ value: { type: "object" } });
  expect(parseJsonField("[1]", true)).toEqual({ error: "Schéma je JSON objekt (JSON Schema nebo příklad)." });
  expect(parseJsonField("[1]", false)).toEqual({ value: [1] });
  expect(parseJsonField("{", false)).toEqual({ error: "Neplatný JSON." });
  expect(parseJsonField("  ", true)).toEqual({ value: undefined });
  expect(pretty({ a: 1 })).toBe('{\n  "a": 1\n}');
});

it("checks retry tries and wait", () => {
  expect(parseRetry("3", "1000")).toEqual({ value: { maxTries: 3, waitMs: 1000 } });
  expect(parseRetry("2", "")).toEqual({ value: { maxTries: 2, waitMs: 0 } });
  expect(parseRetry("", "")).toEqual({ value: undefined });
  expect(parseRetry("0", "")).toEqual({ error: "Počet pokusů je celé číslo od 1." });
  expect(parseRetry("2", "-1")).toEqual({ error: "Čekání je počet milisekund od 0." });
});
