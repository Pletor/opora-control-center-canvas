import { describe, expect, it } from "vitest";
import {
  ACCESS_REQUIRED_EVENT,
  canLogout,
  LOCAL_STATUS,
  MIN_TOKEN_LENGTH,
  lockedOut,
  needsGate,
  statusFrom,
  tokenHint,
  tokenIsUsable,
} from "./access-gate";

const TOKEN = "z".repeat(MIN_TOKEN_LENGTH);

describe("brána vzdáleného přístupu", () => {
  it("se ukáže jen venku a jen bez tokenu", () => {
    expect(needsGate(null)).toBe(false);
    expect(needsGate({ remote: false, authenticated: true, host: "127.0.0.1:8740" })).toBe(false);
    expect(needsGate({ remote: false, authenticated: false, host: "" })).toBe(false);
    expect(needsGate({ remote: true, authenticated: true, host: "a.trycloudflare.com" })).toBe(false);
    expect(needsGate({ remote: true, authenticated: false, host: "a.trycloudflare.com" })).toBe(true);
  });

  it("čte stav tolerantně: co nerozumí, bere jako domácí běh", () => {
    expect(statusFrom(null)).toEqual(LOCAL_STATUS);
    expect(statusFrom("ne")).toEqual(LOCAL_STATUS);
    expect(statusFrom({})).toEqual(LOCAL_STATUS);
    expect(statusFrom({ remote: true })).toEqual({ remote: true, authenticated: false, host: "" });
    expect(statusFrom({ remote: true, authenticated: true, host: "a.trycloudflare.com" })).toEqual({
      remote: true,
      authenticated: true,
      host: "a.trycloudflare.com",
    });
    expect(needsGate(statusFrom(undefined))).toBe(false);
  });

  it("po 401 zamkne i stav, který tvrdil opak", () => {
    expect(lockedOut({ remote: true, authenticated: true, host: "a.trycloudflare.com" })).toEqual({
      remote: true,
      authenticated: false,
      host: "a.trycloudflare.com",
    });
    expect(lockedOut(null)).toEqual({ remote: true, authenticated: false, host: "" });
    expect(needsGate(lockedOut(null))).toBe(true);
  });

  it("odesílá jen token, který má šanci projít", () => {
    expect(tokenIsUsable("")).toBe(false);
    expect(tokenIsUsable("   ")).toBe(false);
    expect(tokenIsUsable("z".repeat(MIN_TOKEN_LENGTH - 1))).toBe(false);
    expect(tokenIsUsable(` ${TOKEN} `)).toBe(true);
    expect(tokenHint("")).toBe("");
    expect(tokenHint(TOKEN)).toBe("");
    expect(tokenHint("krátký")).toContain(String(MIN_TOKEN_LENGTH));
  });

  it("drží jediný název události pro celou aplikaci", () => {
    expect(ACCESS_REQUIRED_EVENT).toBe("opora:access-required");
  });

  it("nabídne odhlášení jen venku s platným přihlášením", () => {
    expect(canLogout(null)).toBe(false);
    expect(canLogout(LOCAL_STATUS)).toBe(false);
    expect(canLogout({ remote: true, authenticated: false, host: "a.trycloudflare.com" })).toBe(false);
    expect(canLogout({ remote: true, authenticated: true, host: "a.trycloudflare.com" })).toBe(true);
  });

  it("po odhlášení je brána zase zamčená pro stejný host", () => {
    const after = lockedOut({ remote: true, authenticated: true, host: "a.trycloudflare.com" });
    expect(needsGate(after)).toBe(true);
    expect(canLogout(after)).toBe(false);
    expect(after.host).toBe("a.trycloudflare.com");
  });
});
