import { describe, expect, it } from "vitest";
import { parseTrend, sparkPath, trendLines, TREND_METRICS } from "./velin-trend";

const at = (hour: number) => `2026-10-28T${String(hour).padStart(2, "0")}:00:00.000Z`;

describe("Trend ve Velínu", () => {
  it("odpověď bez řad nebo s neplatným bodem je null", () => {
    expect(parseTrend({ series: { holes: [{ at: at(9), value: 2 }] } })).toEqual({ holes: [{ at: at(9), value: 2 }] });
    expect(parseTrend({ series: { holes: [{ at: at(9), value: "2" }] } })).toBeNull();
    expect(parseTrend({})).toBeNull();
  });

  it("křivka jde podle času a rozsahu hodnot, jediný bod je rovná čára uprostřed", () => {
    expect(sparkPath([{ at: at(9), value: 4 }, { at: at(10), value: 2 }, { at: at(11), value: 0 }], 100, 20))
      .toBe("M0.0,0.0 L50.0,10.0 L100.0,20.0");
    expect(sparkPath([{ at: at(9), value: 3 }], 100, 20)).toBe("M0.0,10.0 L100.0,10.0");
    expect(sparkPath([], 100, 20)).toBe("");
  });

  it("řádky drží pevné pořadí, poslední hodnotu, rozdíl od prvního vzorku a jeho směr k lepšímu", () => {
    const lines = trendLines({ holes: [{ at: at(9), value: 5 }, { at: at(10), value: 3 }],
      "cards.done": [{ at: at(9), value: 4 }, { at: at(10), value: 2 }] }, 100, 20);
    expect(lines.map(line => line.id)).toEqual(TREND_METRICS.map(metric => metric.id));
    expect(lines[0]).toMatchObject({ last: 3, delta: -2, tone: "better" });
    expect(lines[1]).toMatchObject({ last: null, delta: null, tone: "same", path: "" });
    expect(lines.find(line => line.id === "cards.done")).toMatchObject({ delta: -2, tone: "worse" });
  });
});
