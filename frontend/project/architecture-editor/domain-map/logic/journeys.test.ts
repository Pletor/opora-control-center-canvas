import { describe, expect, it } from "vitest";
import type { ApplicationSite, CustomerJourney } from "@/shared/types/logic/types";
import {
  FROM_NAV, MAX_JOURNEYS, MAX_STEPS, addStep, journeyForSave, oneLine, journeyProblem, journeysForSave, moveStep,
  newJourney, previousStepId, previousStepPage, removeJourney, removeStep, replaceJourney, stepName, stepPageLabel, stepSignal, updateStep,
} from "./journeys";

const app: ApplicationSite = { kind: "application", environments: [{ name: "Vývoj", host: "localhost:3000" }], healthPath: "/api/health" };

/** Trychtýř ze zadání: přistávací stránka → kontakty → prodej → upsell, miniupsell odbočí po prodeji. */
const funnel: CustomerJourney = { id: "kurz", name: "Prodej kurzu", actor: "Začínající zahrádkář",
  pointA: "Rostliny mu hynou.", pointB: "Má zelený balkon.", steps: [
  { id: "vstup", page: "pristavaci", label: "Vstupní stránka", via: { do: "open" } },
  { id: "kontakt", page: "obsah", label: "1. Stránka s obsahem zdarma", via: { do: "click", section: "hero", text: "Chci video" } },
  { id: "prodej", page: "nabidka", label: "Prodej", shift: "Chce kurz.", objection: "Je to drahé?" },
  { id: "upsell", page: "upsell", label: "Upsell" },
  { id: "mini", page: "miniupsell", label: "Miniupsell", after: "prodej", via: { do: "submit", section: "form" } },
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
    const changed = updateStep(funnel, "kontakt", { id: "jine", via: undefined, shift: "Dostane video zdarma." } as never);
    expect(changed.steps[1]).toEqual({ id: "kontakt", page: "obsah", label: "1. Stránka s obsahem zdarma", shift: "Dostane video zdarma." });
  });
  it("odebrání a posun kroku zruší odbočku, která by mířila na chybějící nebo pozdější krok", () => {
    expect(removeStep(funnel, "prodej").steps.find((step) => step.id === "mini")).toEqual({ id: "mini", page: "miniupsell", label: "Miniupsell",
      via: { do: "submit", section: "form" } });
    const moved = moveStep(moveStep(funnel, "mini", -1), "mini", -1);
    expect(moved.steps.map((step) => step.id)).toEqual(["vstup", "kontakt", "mini", "prodej", "upsell"]);
    expect(moved.steps[2].after).toBeUndefined();
    expect(moveStep(funnel, "vstup", -1)).toBe(funnel);
  });
  it("signál přechodu sedí k pořadí: první krok jen otevření, posunutý krok klik ztratí a otevření mimo začátek zmizí", () => {
    const swapped = moveStep(funnel, "kontakt", -1);
    expect(swapped.steps[0]).toEqual({ id: "kontakt", page: "obsah", label: "1. Stránka s obsahem zdarma" });
    expect(swapped.steps[1]).toEqual({ id: "vstup", page: "pristavaci", label: "Vstupní stránka" });
    expect(updateStep(funnel, "vstup", { via: { do: "click" } }).steps[0].via).toBeUndefined();
    expect(updateStep(funnel, "upsell", { via: { do: "submit", section: "smazana" } }).steps[3].via).toEqual({ do: "submit", section: "smazana" });
  });
  it("hlídá název, počet kroků, menu jen na začátku a odbočku dozadu", () => {
    expect(journeyProblem(funnel)).toBeNull();
    expect(journeyProblem({ ...funnel, name: " " })).not.toBeNull();
    expect(journeyProblem({ ...funnel, steps: funnel.steps.slice(0, 1) })).toContain("dvě");
    expect(journeyProblem({ ...funnel, steps: [funnel.steps[0], { id: "x", page: FROM_NAV }] })).toContain("Menu");
    expect(journeyProblem({ ...funnel, steps: [funnel.steps[0], { id: "x", page: "a", after: "x" }] })).toContain("dřívější");
  });
  it("před uložením ořízne texty a prázdné vynechá, bez cest klíč zmizí", () => {
    const raw: CustomerJourney = { id: "c", name: "  Poptávka ", purpose: "  ", actor: " Majitel zahrady ", pointA: "", pointB: " Má plán. ", steps: [
      { id: "a", page: FROM_NAV, label: " Menu ", shift: "", objection: " Spam " },
      { id: "b", page: "p", after: "a", shift: " Chce prohlídku. ", via: { do: "submit", section: "", text: "  Odeslat " } }] };
    expect(journeyForSave(raw)).toEqual({ id: "c", name: "Poptávka", actor: "Majitel zahrady", pointB: "Má plán.", steps: [
      { id: "a", page: FROM_NAV, label: "Menu", objection: "Spam" },
      { id: "b", page: "p", shift: "Chce prohlídku.", via: { do: "submit", text: "Odeslat" }, after: "a" }] });
    expect(journeysForSave({ ...app, journeys: [raw] }).journeys?.[0].name).toBe("Poptávka");
    expect("journeys" in journeysForSave({ ...app, journeys: [] })).toBe(false);
  });
  it("krok navazuje na odbočku nebo předchozí krok a akci dělá zákazník na jeho stránce", () => {
    expect(previousStepId(funnel, 0)).toBeNull();
    expect(previousStepId(funnel, 4)).toBe("prodej");
    expect(previousStepPage(funnel, 0)).toBeNull();
    expect(previousStepPage(funnel, 1)).toBe("pristavaci");
    expect(previousStepPage(funnel, 4)).toBe("nabidka");
  });
  it("text z odstavce nenese řídicí znaky", () => {
    expect(oneLine("Bojí se\nspamu\t a cen")).toBe("Bojí se spamu  a cen");
  });
  it("signál kroku čte sekce stránky předchozího kroku, první krok a krok bez via signál nemají", () => {
    const pages = [{ id: "pristavaci", site: { kind: "page" as const, path: "/", sections: [{ id: "hero", role: "hero" as const, name: "Úvod", intent: "" }] } }];
    expect(stepSignal(funnel, 1, pages)).toEqual({ text: "klikne na „Chci video“ v sekci Úvod", missingSection: null });
    expect(stepSignal(funnel, 4, pages)).toEqual({ text: "odešle formulář v sekci form", missingSection: "form" });
    expect(stepSignal(funnel, 0, pages)).toBeNull();
    expect(stepSignal(funnel, 3, pages)).toBeNull();
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
