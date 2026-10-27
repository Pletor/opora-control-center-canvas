import { describe, expect, it } from "vitest";
import { MAX_INV_ZOOM, MIN_INV_ZOOM, inverseZoom, portLabel, portTitle } from "./port-labels";

describe("portLabel", () => {
  it("pojmenuje druhy portů česky", () => {
    expect(portLabel("next")).toBe("Další krok");
    expect(portLabel("action")).toBe("Akce");
    expect(portLabel("rule")).toBe("Pravidlo");
    expect(portLabel("flow")).toBe("Tok mezi oblastmi");
    expect(portLabel("material")).toBe("Podklady");
  });
  it("port bloku nese své jméno, bez jména obecný popisek", () => {
    expect(portLabel("block", "  Splněno ")).toBe("Splněno");
    expect(portLabel("block", "")).toBe("Port bloku");
  });
  it("jméno ostatní druhy nemění", () => {
    expect(portLabel("next", "cokoli")).toBe("Další krok");
  });
});

describe("portTitle", () => {
  it("připojí nápovědu za název", () => {
    expect(portTitle("next", "", "tahem propojit")).toBe("Další krok · tahem propojit");
    expect(portTitle("action")).toBe("Akce");
  });
});

describe("inverseZoom", () => {
  it("při zoomu 1 je 1, při 2 je 0,5, při 0,5 je 2", () => {
    expect(inverseZoom(1)).toBe(1);
    expect(inverseZoom(2)).toBe(0.5);
    expect(inverseZoom(0.5)).toBe(2);
  });
  it("hodnotu omezí a nesmyslný zoom nahradí 1", () => {
    expect(inverseZoom(0.01)).toBe(MAX_INV_ZOOM);
    expect(inverseZoom(100)).toBe(MIN_INV_ZOOM);
    expect(inverseZoom(0)).toBe(1);
    expect(inverseZoom(Number.NaN)).toBe(1);
  });
});
