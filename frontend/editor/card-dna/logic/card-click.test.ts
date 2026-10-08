import { describe, expect, it } from "vitest";
import { cardClickAction, isCardControl, shouldActivateDialog } from "./card-click";

describe("klik na kompaktní kartu bez časovače", () => {
  it("první klik otevře náhled; druhý jej zruší a vstoupí dovnitř bez ohledu na interval", () => {
    for (const elapsed of [10, 221, 500, 1500]) {
      let popup = false; let entered = false;
      for (const event of [{ detail: 1, timeStamp: 0 }, { detail: 2, timeStamp: elapsed }]) {
        const action = cardClickAction(event);
        if (action === "preview") popup = true;
        if (action === "enter") { popup = false; entered = true; }
      }
      expect(popup).toBe(false); expect(entered).toBe(true);
    }
  });
  it.each(["[data-block-id]", ".react-flow__handle", ".node-card__port", ".node-card__port-label", "button", "input", "a"])("%s neotevře popup ani nevstoupí dovnitř", selector => {
    const target = { closest: (selectors: string) => selectors.split(", ").includes(selector) ? {} : null };
    expect(isCardControl(target)).toBe(true);
    expect(cardClickAction({ detail: 1, excluded: isCardControl(target) })).toBe("ignore");
    expect(cardClickAction({ detail: 2, excluded: isCardControl(target) })).toBe("ignore");
  });
  it("modifikátor jen vybírá a trojklik znovu neotevře DNA", () => {
    expect(cardClickAction({ detail: 1, modified: true })).toBe("ignore");
    expect(cardClickAction({ detail: 3 })).toBe("ignore");
  });
  it("dokud ukazatel zůstává na kartě, náhled nesmí zablokovat druhý klik", () => {
    const rect = { left: 10, top: 20, right: 200, bottom: 300 };
    expect(shouldActivateDialog(rect, { x: 80, y: 90 })).toBe(false);
    expect(shouldActivateDialog(rect, { x: 201, y: 90 })).toBe(true);
  });
});
