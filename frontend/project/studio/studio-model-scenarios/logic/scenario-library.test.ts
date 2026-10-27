import { describe, expect, it } from "vitest";
import { scenarios } from "../../model/simulation/logic";
import { ALL_CATEGORIES, filterScenarios, isScenarioDomain, scenarioCategories, scenarioDomain, scenarioDomainName } from "./scenario-library";

describe("scenario library", () => {
  it("gives every scenario its own model domain next to architecture domains", () => {
    expect(scenarioDomain("web-chain")).toBe("scenario:web-chain");
    expect(isScenarioDomain("scenario:web-chain")).toBe(true);
    expect(isScenarioDomain("web")).toBe(false);
    expect(scenarios.every((s) => scenarioDomain(s.id).length <= 128)).toBe(true);
    expect(scenarioDomainName({ name: "Web · cesta" })).toBe("MODEL · Web · cesta");
  });

  it("filters by category and text", () => {
    const categories = scenarioCategories(scenarios);
    expect(categories[0]).toBe(ALL_CATEGORIES);
    expect(categories).toContain("Web");
    expect(filterScenarios(scenarios, "", ALL_CATEGORIES)).toHaveLength(scenarios.length);
    expect(filterScenarios(scenarios, "", "Web").every((s) => s.category === "Web")).toBe(true);
    expect(filterScenarios(scenarios, "POSTGRESQL", ALL_CATEGORIES).map((s) => s.id)).toContain("web-chain");
    expect(filterScenarios(scenarios, "nic-takoveho", ALL_CATEGORIES)).toEqual([]);
  });
});
