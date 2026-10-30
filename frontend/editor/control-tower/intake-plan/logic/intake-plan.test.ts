import { describe, expect, it } from "vitest";
import { criteriaDone, intakePlan, parseIntake, summaryParts } from "./intake-plan";
import { intakeFixture } from "./intake-fixture";
import { briefFixture } from "../brief-panel/logic/brief-fixture";

const names: Record<string, string> = { k1: "Sloupec vector(1024)", k2: "Hledání podle modelu" };
const nameOf = (id: string) => names[id] ?? id;
describe("Požadavky a plán", () => {
  const plan = intakePlan(intakeFixture, nameOf);

  it("aktivní milník: postup, kritéria hotovo/nehotovo a jména karet z grafu", () => {
    const milestone = plan.areas[0].milestone!;
    expect(milestone).toMatchObject({ id: "ms_1", progress: 50, done: false });
    expect(milestone.criteria.map(item => [item.text, item.done, item.cards.map(card => [card.name, card.done])])).toEqual([
      ["Sloupec 1024", true, [["Sloupec vector(1024)", true]]], ["Hledání čte jen aktuální model", false, [["Hledání podle modelu", false]]]]);
    expect(criteriaDone(milestone)).toBe("1/2 kritérií");
  });

  it("návrh srdce: karty jako ID bez stavu, neznámá karta zůstane pod ID", () => {
    const proposal = plan.areas[1].proposed[0];
    expect(proposal.progress).toBeNull();
    expect(proposal.criteria[0].done).toBeNull();
    expect(proposal.criteria[0].cards).toEqual([{ id: "k2", name: "Hledání podle modelu", done: null }, { id: "neznámá", name: "neznámá", done: null }]);
  });

  it("podmínka otevření: známý milník jménem, jiný text doslova", () => {
    expect(plan.areas[0].deferred[0].condition).toBe("otevře se po splnění milníku „bge-m3 lokálně“");
    expect(plan.areas[1].deferred[0].condition).toBe("podmínka otevření: až bude review");
    expect(plan.areas[0].requirements[0].condition).toBeNull();
  });

  it("prázdná oblast a jméno z ID, požadavky bez oblasti zvlášť", () => {
    expect(plan.areas.map(area => area.empty)).toEqual([false, false, true]);
    expect(plan.areas[2].name).toBe("a3");
    expect(plan.unassigned.map(item => item.id)).toEqual(["rq_4"]);
  });

  it("souhrn: nové vstupy = nepotvrzené srdcem, pending a duplicity ze serveru", () => {
    expect(plan.summary).toEqual({ entries: 3, fresh: 2, pending: 1, duplicates: 1 });
    expect(summaryParts(plan.summary).map(part => part.text)).toEqual(["2 nové vstupy", "1 čeká na stanovisko", "1 duplicita"]);
    expect(summaryParts({ entries: 0, fresh: 0, pending: 0, duplicates: 7 }).map(part => part.text)).toEqual(["0 nových vstupů", "0 čeká na stanovisko", "7 duplicit"]);
  });

  it("neplatná odpověď hází českou chybu", () => {
    expect(() => parseIntake({ areas: "x" })).toThrow("neplatnou odpověď");
    expect(parseIntake(intakeFixture)).toBe(intakeFixture);
  });
});

it("požadavek nese výslech srdce jako model panelu, bez spisu null", () => {
  const plan = intakePlan({ ...intakeFixture, unassigned: [{ ...intakeFixture.unassigned[0], brief: briefFixture }] }, nameOf);
  expect(plan.areas[0].requirements[0].brief).toBeNull();
  expect(plan.unassigned[0].brief).toMatchObject({ status: "grilling", tone: "ask", open: [{ id: "q2" }] });
});
