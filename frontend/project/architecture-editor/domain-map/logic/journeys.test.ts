import { describe, expect, it } from "vitest";
import type { ApplicationSite, CustomerJourney } from "@/shared/types/logic/types";
import {
  FROM_NAV, MAX_JOURNEYS, MAX_STEPS, addStep, formatCount, formatRate, journeyForSave, journeyProblem, journeysForSave, moveStep,
  newJourney, previousStepId, removeJourney, removeStep, replaceJourney, stepName, stepPageLabel, stepRate, updateStep,
} from "./journeys";

const app: ApplicationSite = { kind: "application", environments: [{ name: "Vývoj", host: "localhost:3000" }], healthPath: "/api/health" };

/** Trychtýř ze zadání: přistávací stránka → kontakty → prodej → upsell, miniupsell odbočí po prodeji. */
const funnel: CustomerJourney = { id: "kurz", name: "Prodej kurzu", steps: [
  { id: "vstup", page: "pristavaci", label: "Vstupní stránka", count: 36879 },
  { id: "kontakt", page: "obsah", label: "1. Stránka s obsahem zdarma", count: 18975 },
  { id: "prodej", page: "nabidka", label: "Prodej", count: 3369 },
  { id: "upsell", page: "upsell", label: "Upsell", count: 1187 },
  { id: "mini", page: "miniupsell", label: "Miniupsell", count: 1545, after: "prodej" },
] };

describe("cesty zákazníka jako trychtýř", () => {
  it("nová cesta vede z menu na poslední stránku, s volným id a bez stránek ani nad stropem nevznikne", () => {
    expect(newJourney(app, ["home", "dekujeme"])).toEqual({ id: "cesta-1", name: "Nová cesta",
      steps: [{ id: "krok-1", page: FROM_NAV }, { id: "krok-2", page: "dekujeme" }] });
    const one = replaceJourney(app, newJourney(app, ["a"])!);
    expect(one.healthPath).toBe("/api/health");
    expect(newJourney(one, ["a"])?.id).toBe("cesta-2");
    expect(newJourney(app, [])).toBeNull();
    const full = { ...app, journeys: Array.from({ length: MAX_JOURNEYS }, (_, i) => ({ ...funnel, id: "c" + i })) };
    expect(newJourney(full, ["a"])).toBeNull();
  });
  it("uložení cesty nahradí tu se stejným id, odebrání poslední smaže klíč", () => {
    const one = replaceJourney(app, funnel);
    const renamed = replaceJourney(one, { ...funnel, name: "Jiný název" });
    expect(renamed.journeys?.map((journey) => journey.name)).toEqual(["Jiný název"]);
    expect("journeys" in removeJourney(renamed, "kurz")).toBe(false);
  });
  it("přidá krok s ještě nepoužitou stránkou a drží strop kroků", () => {
    const added = addStep({ ...funnel, steps: funnel.steps.slice(0, 2) }, ["pristavaci", "obsah", "nabidka"]);
    expect(added.steps[2]).toEqual({ id: "krok-1", page: "nabidka" });
    const full = { ...funnel, steps: Array.from({ length: MAX_STEPS }, (_, i) => ({ id: "s" + i, page: "p" })) };
    expect(addStep(full, ["p"])).toBe(full);
  });
  it("úprava kroku nepřepíše id a prázdné pole z kroku zmizí", () => {
    const changed = updateStep(funnel, "kontakt", { id: "jine", count: undefined, experience: "Dostane video zdarma." } as never);
    expect(changed.steps[1]).toEqual({ id: "kontakt", page: "obsah", label: "1. Stránka s obsahem zdarma", experience: "Dostane video zdarma." });
  });
  it("odebrání a posun kroku zruší odbočku, která by mířila na chybějící nebo pozdější krok", () => {
    expect(removeStep(funnel, "prodej").steps.find((step) => step.id === "mini")).toEqual({ id: "mini", page: "miniupsell", label: "Miniupsell", count: 1545 });
    const moved = moveStep(moveStep(funnel, "mini", -1), "mini", -1);
    expect(moved.steps.map((step) => step.id)).toEqual(["vstup", "kontakt", "mini", "prodej", "upsell"]);
    expect(moved.steps[2].after).toBeUndefined();
    expect(moveStep(funnel, "vstup", -1)).toBe(funnel);
  });
  it("hlídá název, počet kroků, menu jen na začátku a odbočku dozadu", () => {
    expect(journeyProblem(funnel)).toBeNull();
    expect(journeyProblem({ ...funnel, name: " " })).not.toBeNull();
    expect(journeyProblem({ ...funnel, steps: funnel.steps.slice(0, 1) })).toContain("dvě");
    expect(journeyProblem({ ...funnel, steps: [funnel.steps[0], { id: "x", page: FROM_NAV }] })).toContain("Menu");
    expect(journeyProblem({ ...funnel, steps: [funnel.steps[0], { id: "x", page: "a", after: "x" }] })).toContain("dřívější");
  });
  it("před uložením ořízne texty a prázdné vynechá, bez cest klíč zmizí", () => {
    const raw: CustomerJourney = { id: "c", name: "  Poptávka ", purpose: "  ", steps: [
      { id: "a", page: FROM_NAV, label: " Menu ", experience: "" }, { id: "b", page: "p", count: 0, after: "a" }] };
    expect(journeyForSave(raw)).toEqual({ id: "c", name: "Poptávka", steps: [{ id: "a", page: FROM_NAV, label: "Menu" }, { id: "b", page: "p", count: 0, after: "a" }] });
    expect(journeysForSave({ ...app, journeys: [raw] }).journeys?.[0].name).toBe("Poptávka");
    expect("journeys" in journeysForSave({ ...app, journeys: [] })).toBe(false);
  });
  it("konverze se počítá proti kroku, na který krok navazuje, a jen s oběma počty", () => {
    expect(previousStepId(funnel, 0)).toBeNull();
    expect(previousStepId(funnel, 4)).toBe("prodej");
    expect(formatRate(stepRate(funnel, 1)!)).toBe("51,5 %");
    expect(formatRate(stepRate(funnel, 4)!)).toBe("45,9 %");
    expect(stepRate(funnel, 0)).toBeNull();
    expect(stepRate({ ...funnel, steps: [{ ...funnel.steps[0], count: 0 }, funnel.steps[1]] }, 1)).toBeNull();
    expect(stepRate({ ...funnel, steps: [funnel.steps[0], { id: "x", page: "p" }] }, 1)).toBeNull();
    expect(formatCount(36879)).toBe("36 879");
    expect(formatCount(1187)).toBe("1 187");
    expect(formatCount(18)).toBe("18");
  });
  it("pojmenuje stránku kroku i chybějící stránku a krok podle role nebo pořadí", () => {
    const pages = [{ id: "a", name: "Kontakt" }];
    expect(stepPageLabel(FROM_NAV, pages)).toEqual({ label: "Menu", missing: false });
    expect(stepPageLabel("a", pages)).toEqual({ label: "Kontakt", missing: false });
    expect(stepPageLabel("pryc", pages).missing).toBe(true);
    expect(stepName(funnel, "prodej")).toBe("Prodej");
    expect(stepName({ ...funnel, steps: [{ id: "x", page: "p" }] }, "x")).toBe("1. krok");
  });
});
