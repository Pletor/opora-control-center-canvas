import { describe, expect, it } from "vitest";
import { FAR_ZOOM, blocksDetail, cardDetail, farZoomSelector, portEditorsShown } from "./card-lod";

describe("card level of detail", () => {
  it("flips only at the zoom threshold, not with every zoom step", () => {
    const at = (zoom: number) => farZoomSelector({ transform: [0, 0, zoom] });
    expect(at(1)).toBe(false);
    expect(at(FAR_ZOOM)).toBe(false);
    expect(at(FAR_ZOOM - 0.01)).toBe(true);
    // Dva různé zoomy pod prahem dávají stejnou hodnotu: `useStore` kartu nepřekreslí.
    expect(at(0.2)).toBe(at(0.3));
  });

  it("keeps the selected card full at any zoom", () => {
    expect(cardDetail(true, false)).toBe("far");
    expect(cardDetail(true, true)).toBe("full");
    expect(cardDetail(false, false)).toBe("full");
  });

  it("keeps a dirty or focused port editor mounted after deselect", () => {
    expect(portEditorsShown("full", false)).toBe(true);
    expect(portEditorsShown("row", false)).toBe(false);
    expect(portEditorsShown("row", true)).toBe(true);
    expect(portEditorsShown("far", true)).toBe(true);
  });

  it("keeps blocks with a draft or focus full while the card is far", () => {
    expect(blocksDetail("far", false)).toBe("far");
    expect(blocksDetail("far", true)).toBe("full");
    expect(blocksDetail("full", false)).toBe("full");
  });
});
