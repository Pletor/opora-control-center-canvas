import { describe, expect, it } from "vitest";
import { settingsRequested, underlyingScreen } from "./settings-route";

describe("global settings navigation", () => {
  it("opens the standalone page and accepts the former entry link", () => {
    for (const value of ["screen=settings", "screen=home&entry=settings"]) {
      const query = new URLSearchParams(value);
      expect(settingsRequested(query)).toBe(true);
      expect(underlyingScreen(query)).toBe("home");
    }
  });
  it.each(["home", "canvas", "heart"])("restores underlying %s on reload", (screen) => {
    expect(underlyingScreen(new URLSearchParams(`screen=settings&returnScreen=${screen}&workspace=main`))).toBe(screen);
  });
  it("keeps explicit project links and defaults direct settings to home", () => {
    expect(underlyingScreen(new URLSearchParams("screen=settings&workspace=main"))).toBe("home");
    expect(underlyingScreen(new URLSearchParams("workspace=main"))).toBe("canvas");
    expect(settingsRequested(new URLSearchParams("screen=canvas"))).toBe(false);
  });
});
