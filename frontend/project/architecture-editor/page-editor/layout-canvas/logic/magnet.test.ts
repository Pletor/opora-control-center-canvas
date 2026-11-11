import { describe, expect, it } from "vitest";
import { magnet } from "./magnet";

const header = { x: 0, y: 0, w: 12, h: 2 };
const side = { x: 8, y: 2, w: 4, h: 4 };

describe("magnet", () => {
  it("box blíž než buňku od hrany souseda k ní přilne, dál se jen zaokrouhlí", () => {
    expect(magnet({ x: 0.4, y: 2.8, w: 4, h: 2 }, [header], "move")).toEqual({ x: 0, y: 2, w: 4, h: 2 });
    expect(magnet({ x: 3.3, y: 3.6, w: 4, h: 2 }, [header, side], "move")).toEqual({ x: 4, y: 4, w: 4, h: 2 });
    expect(magnet({ x: 2.5, y: 5.6, w: 2, h: 2 }, [], "move")).toEqual({ x: 3, y: 6, w: 2, h: 2 });
  });
  it("pravá hrana se zarovná k okraji rodiče i k sousedovi", () => {
    expect(magnet({ x: 7.3, y: 2, w: 4, h: 2 }, [], "move").x).toBe(8);
    expect(magnet({ x: 0, y: 2, w: 7.4, h: 3.5 }, [header, side], "resize")).toEqual({ x: 0, y: 2, w: 8, h: 4 });
  });
  it("změna velikosti nepohne polohou a drží box v mřížce", () => {
    expect(magnet({ x: 6, y: 1, w: 9.2, h: 0.1 }, [], "resize")).toEqual({ x: 6, y: 1, w: 6, h: 1 });
  });
});
