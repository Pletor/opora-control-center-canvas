import { describe, expect, it } from "vitest";
import { fold, heardCommand, stripWake } from "./wake-word";

describe("stripWake", () => {
  it("najde oslovení kdekoli ve větě bez ohledu na diakritiku a velikost", () => {
    expect(stripWake("Pletore, co dělá srdce?")).toBe("co dělá srdce?");
    expect(stripWake("PLETOŘE ukaž plán")).toBe("ukaž plán");
    expect(stripWake("ukaž plán, Jarvisi")).toBe("ukaž plán,");
    expect(stripWake("a co ty, pletor")).toBe("a co ty,");
  });
  it("bez oslovení vrátí null", () => {
    expect(stripWake("co dělá srdce")).toBeNull();
    expect(stripWake("pletorovi se to líbí")).toBeNull();
  });
});

describe("heardCommand", () => {
  const base = { wakeOnly: false, last: null, now: 10_000 };
  it("krátký šum zahodí, normální větu pošle", () => {
    expect(heardCommand(" a ", base)).toBeNull();
    expect(heardCommand("ano", base)).toBe("ano");
  });
  it("stejnou větu do 2 s zahodí, po 2 s ji pošle znovu", () => {
    const last = { text: "Ukaž plán", at: 9_000 };
    expect(heardCommand("ukaž plán", { ...base, last })).toBeNull();
    expect(heardCommand("ukaž plán", { ...base, last, now: 11_500 })).toBe("ukaž plán");
    expect(heardCommand("jiná věta", { ...base, last })).toBe("jiná věta");
  });
  it("jen na oslovení: bez oslovení nic, s oslovením věta bez něj; samotné oslovení nic", () => {
    const wake = { ...base, wakeOnly: true };
    expect(heardCommand("co dělá srdce", wake)).toBeNull();
    expect(heardCommand("Pletore, co dělá srdce", wake)).toBe("co dělá srdce");
    expect(heardCommand("Pletore!", wake)).toBeNull();
  });
  it("fold sjednotí diakritiku", () => {
    expect(fold(" Jarvisi ")).toBe("jarvisi");
    expect(fold("Řekni")).toBe("rekni");
  });
});
