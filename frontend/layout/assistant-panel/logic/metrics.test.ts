import { describe, expect, it } from "vitest";
import { contextUsage, metricCost, metricNumber, totalTokens } from "./metrics";

describe("assistant metrics", () => {
  it("distinguishes missing telemetry from measured zero", () => {
    expect(totalTokens()).toBeNull();
    expect(metricNumber(undefined)).toBe("—");
    expect(metricNumber(0)).toBe("0");
    expect(metricCost(undefined)).toBe("nedostupný");
  });
  it("sums all models including cache without using last-turn usage", () => {
    const model = { inputTokens: 10, outputTokens: 20, cacheReadInputTokens: 30, cacheCreationInputTokens: 40 };
    expect(totalTokens({ models: { main: model, helper: model }, lastUsage: { input_tokens: 999 } })).toBe(200);
    expect(totalTokens({ models: { main: { inputTokens: 10 } } })).toBeNull();
  });
  it("uses only the actual main model capacity, never an alias or another model", () => {
    const models = { actual: { contextWindow: 200000 } };
    expect(contextUsage({ model: "actual", models, contextTokens: 50000 }).percent).toBe(25);
    expect(contextUsage({ model: "opus", models, contextTokens: 50000 }).percent).toBeNull();
    expect(contextUsage({ model: "actual", models }).percent).toBeNull();
  });
});
