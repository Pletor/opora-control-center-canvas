import { describe, expect, it } from "vitest";
import { mapRefreshPayload, mapRefreshView, parseMapRefreshConfig } from "./map-refresh-config";

describe("map-refresh-config", () => {
  it("čte jen explicitní boolean ze serveru", () => {
    expect(parseMapRefreshConfig({ enabled: true })).toEqual({ enabled: true });
    expect(parseMapRefreshConfig({ enabled: false })).toEqual({ enabled: false });
    expect(parseMapRefreshConfig({ enabled: 1 })).toBeNull();
    expect(parseMapRefreshConfig(null)).toBeNull();
  });

  it("nenačtený stav se nevydává za vypnutou automatiku", () => {
    expect(mapRefreshView(null)).toMatchObject({ checked: false, busy: true });
  });

  it("zapnutá a vypnutá automatika mají vlastní větu a polohu", () => {
    expect(mapRefreshView({ enabled: true })).toMatchObject({ checked: true, busy: false });
    const off = mapRefreshView({ enabled: false });
    expect(off.checked).toBe(false);
    expect(off.detail).toContain("Aktualizovat teď");
  });

  it("tělo přepnutí má právě pole enabled", () => {
    expect(mapRefreshPayload(false)).toEqual({ enabled: false });
  });
});
