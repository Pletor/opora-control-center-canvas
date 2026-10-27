import { describe, expect, it } from "vitest";
import type { ApplicationSite } from "@/shared/types/logic/types";
import { FROM_NAV, MAX_JOURNEYS, addJourney, journeyEndLabel, journeyProblem, journeysForSave, removeJourney, updateJourney } from "./journeys";

const app: ApplicationSite = { kind: "application", environments: [{ name: "Vývoj", host: "localhost:3000" }], healthPath: "/api/health" };

describe("cesty zákazníka", () => {
  it("přidá cestu z menu na poslední stránku s volným id a zachová zbytek site", () => {
    const one = addJourney(app, ["home", "dekujeme"]);
    expect(one.journeys).toEqual([{ id: "cesta-1", name: "Nová cesta", from: FROM_NAV, to: "dekujeme" }]);
    expect(one.healthPath).toBe("/api/health");
    expect(addJourney(one, ["home"]).journeys?.map((journey) => journey.id)).toEqual(["cesta-1", "cesta-2"]);
  });
  it("bez stránek a nad stropem nic nepřidá", () => {
    expect(addJourney(app, [])).toBe(app);
    let site = app;
    for (let i = 0; i < MAX_JOURNEYS + 2; i += 1) site = addJourney(site, ["a"]);
    expect(site.journeys).toHaveLength(MAX_JOURNEYS);
  });
  it("úprava nepřepíše id, odebrání poslední cesty smaže klíč", () => {
    const one = addJourney(app, ["a"]);
    const renamed = updateJourney(one, "cesta-1", { name: "Poptávka", from: "a", id: "jine" } as never);
    expect(renamed.journeys?.[0]).toEqual({ id: "cesta-1", name: "Poptávka", from: "a", to: "a" });
    expect("journeys" in removeJourney(renamed, "cesta-1")).toBe(false);
  });
  it("před uložením ořízne název a prázdný seznam vynechá", () => {
    expect(journeysForSave({ ...app, journeys: [{ id: "c", name: "  Poptávka ", from: "nav", to: "b" }] }).journeys?.[0].name).toBe("Poptávka");
    expect("journeys" in journeysForSave({ ...app, journeys: [] })).toBe(false);
  });
  it("hlídá stejný začátek a cíl a pojmenuje chybějící stránku", () => {
    expect(journeyProblem({ id: "c", name: "x", from: "a", to: "a" })).not.toBeNull();
    expect(journeyProblem({ id: "c", name: "x", from: "nav", to: "a" })).toBeNull();
    const pages = [{ id: "a", name: "Kontakt" }];
    expect(journeyEndLabel("nav", pages)).toEqual({ label: "Menu", missing: false });
    expect(journeyEndLabel("a", pages)).toEqual({ label: "Kontakt", missing: false });
    expect(journeyEndLabel("pryc", pages).missing).toBe(true);
  });
});
