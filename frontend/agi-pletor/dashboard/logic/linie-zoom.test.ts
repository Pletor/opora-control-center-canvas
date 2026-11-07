import { describe, expect, it } from "vitest";
import { PAD, ZOOM_MAX_SPAN, ticks, tOf, widthText, xOf, zoomAt, zoomLimits } from "./linie-zoom";

const H = 3600e3;
const t0 = Date.parse("2026-11-06T08:00:00Z");

describe("časová souřadnice a přiblížení", () => {
  it("xOf a tOf jsou inverzní", () => {
    const s = { t0, k: 100 / H };
    expect(xOf(s, t0)).toBe(PAD);
    expect(tOf(s, xOf(s, t0 + 3 * H))).toBeCloseTo(t0 + 3 * H);
  });
  it("zoom kolem kurzoru drží čas pod kurzorem", () => {
    const s = { t0, k: 100 / H }, limits = { min: 1e-9, max: 1 };
    for (const [scroll, cursor, factor] of [[0, 300, 1.25], [450, 120, 0.8], [1200, 640, 2]]) {
      const before = tOf(s, scroll + cursor);
      const next = zoomAt(s, scroll, cursor, factor, limits);
      expect(next.k).toBeCloseTo(s.k * factor);
      expect(tOf({ t0, k: next.k }, next.scrollLeft + cursor)).toBeCloseTo(before);
    }
  });
  it("meze: 1× = vše se vejde, nejblíž 15 min přes plátno; krátká data meze slijí", () => {
    const limits = zoomLimits(10 * H, 1000);
    expect(limits.min).toBeCloseTo((1000 - 2 * PAD) / (10 * H));
    expect(limits.max).toBeCloseTo(1000 / ZOOM_MAX_SPAN);
    const s = { t0, k: limits.min };
    expect(zoomAt(s, 0, 200, 1e6, limits).k).toBe(limits.max);
    expect(zoomAt(s, 0, 200, 1e-6, limits).k).toBe(limits.min);
    const short = zoomLimits(5 * 60e3, 1000);
    expect(short.min).toBe(short.max);
  });
  it("značky osy podle hustoty: 5 min zblízka, 6 h zdálky, nikdy hustěji než 84 px", () => {
    const near = ticks({ t0, k: 1000 / ZOOM_MAX_SPAN }, t0, t0 + 15 * 60e3);
    expect(near[1].x - near[0].x).toBeCloseTo(1000 / 3);
    const far = ticks({ t0, k: 600 / (48 * H) }, t0, t0 + 48 * H);
    expect(far[1].x - far[0].x).toBeGreaterThanOrEqual(84);
    expect(far.every((tick) => /^\d\d:\d\d$|^\d+\. \d+\.$/.test(tick.text))).toBe(true);
    expect(widthText(100 / H, 1030)).toBe("10,3 h na šířku");
    expect(widthText(1000 / ZOOM_MAX_SPAN, 1000)).toBe("15 min na šířku");
  });
});
