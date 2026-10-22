import { describe, expect, it, vi } from "vitest";
import { openCardDrawer, setCardDrawerFallback, setCardDrawerHandler } from "./open";

describe("openCardDrawer", () => {
  it("předá požadavek registrovanému drawer a po odregistraci vrací false", () => {
    const seen = vi.fn();
    const off = setCardDrawerHandler(seen);
    expect(openCardDrawer("a", "kroky")).toBe(true);
    expect(seen).toHaveBeenCalledWith({ nodeId: "a", tab: "kroky" });
    off();
    expect(openCardDrawer("a")).toBe(false);
  });

  it("starší odregistrace nesmaže novější příjemce", () => {
    const off = setCardDrawerHandler(() => {});
    const later = vi.fn();
    const offLater = setCardDrawerHandler(later);
    off();
    expect(openCardDrawer("b")).toBe(true);
    expect(later).toHaveBeenCalledWith({ nodeId: "b" });
    offLater();
  });

  it("drawer má přednost před náhradou, náhrada platí bez draweru", () => {
    const backup = vi.fn(), drawer = vi.fn();
    const offFallback = setCardDrawerFallback(backup);
    openCardDrawer("c");
    const offDrawer = setCardDrawerHandler(drawer);
    openCardDrawer("d", "beh");
    expect(backup).toHaveBeenCalledWith({ nodeId: "c" });
    expect(drawer).toHaveBeenCalledWith({ nodeId: "d", tab: "beh" });
    offDrawer(); offFallback();
  });
});
