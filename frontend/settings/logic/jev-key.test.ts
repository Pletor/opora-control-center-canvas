import { describe, expect, it } from "vitest";
import { MAX_JEV_KEY, jevKeyHint, jevKeyIsUsable, jevKeyPayload, jevKeyRows, parseJevStatus } from "./jev-key";

const status = { configured: false, provider: "typesafe", keys: { typesafe: false, celeris: true } };

describe("klíč Jev v Nastavení", () => {
  it("čte jen booleany ze stavu Jev, cizí tvar je neznámý stav", () => {
    expect(parseJevStatus(status)).toEqual(status);
    expect(parseJevStatus({ configured: true, provider: "typesafe" })).toEqual({
      configured: true, provider: "typesafe", keys: { typesafe: true, celeris: false },
    });
    expect(parseJevStatus({ configured: "ano", provider: "typesafe" })).toBeNull();
    expect(parseJevStatus({ configured: true, provider: "openai" })).toBeNull();
    expect(parseJevStatus({})).toBeNull();
    expect(parseJevStatus(null)).toBeNull();
  });

  it("stav nikdy nenese hodnotu klíče, ani když ji server omylem pošle", () => {
    const parsed = parseJevStatus({ ...status, key: "tajne", keys: { typesafe: "tajne", celeris: true } });
    expect(JSON.stringify(parsed)).not.toContain("tajne");
    expect(parsed?.keys.typesafe).toBe(false);
  });

  it("pustí jen klíč, který backend přijme", () => {
    expect(jevKeyIsUsable("")).toBe(false);
    expect(jevKeyIsUsable("   ")).toBe(false);
    expect(jevKeyIsUsable(" ts-abc ")).toBe(true);
    expect(jevKeyHint("ts abc")).toBe("Klíč nesmí obsahovat mezery.");
    expect(jevKeyHint("x".repeat(MAX_JEV_KEY + 1))).toBe(`Klíč má nejvýš ${MAX_JEV_KEY} znaků.`);
    expect(jevKeyHint("")).toBe("");
  });

  it("tělo POST nese oříznutý klíč nebo null a vždy poskytovatele", () => {
    expect(jevKeyPayload(" ts-abc ", "typesafe")).toEqual({ key: "ts-abc", provider: "typesafe" });
    expect(jevKeyPayload(null, "celeris")).toEqual({ key: null, provider: "celeris" });
  });

  it("aktivní poskytovatel je první a stav je jen nastavený / nenastavený", () => {
    expect(jevKeyRows({ ...status, provider: "celeris", configured: true })).toEqual([
      { provider: "celeris", label: "Celeris", active: true, configured: true, state: "Klíč je nastavený" },
      { provider: "typesafe", label: "TypeSafe", active: false, configured: false, state: "Klíč není nastavený" },
    ]);
  });
});
