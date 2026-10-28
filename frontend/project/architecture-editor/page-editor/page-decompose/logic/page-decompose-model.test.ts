import { describe, expect, it } from "vitest";
import { pageComponents, pageDecomposeFacts, pageHoles } from "./page-decompose-model";
import { CHECK, GRAPH } from "./page-decompose-fixture";

describe("podklady rozkladu stránky", () => {
  it("vezme cíl, působení, sekce a cestu přes stránku", () => {
    const facts = pageDecomposeFacts(GRAPH, "p1", CHECK)!;
    expect(facts).toMatchObject({ pageId: "p1", name: "Pěstování", path: "/pestovani", goal: "Návštěvník si vyžádá radu", feel: "klidně" });
    expect(facts.sections.map((section) => section.id)).toEqual(["hero", "cta"]);
    expect(facts.journeys).toHaveLength(1);
    expect(facts.journeys[0]).toMatchObject({ journeyId: "j1", step: 2, role: "Zájem", actor: "Začínající zahrádkář", objection: "Zase spam" });
    expect(facts.journeys[0].next.map((next) => [next.pageId, next.signal?.text])).toEqual([["p2", "klikne na „Chci poradit“ v sekci Výzva"]]);
  });

  it("komponenty jen s touto nejbližší stránkou, s vazbami nesoucími carries", () => {
    expect(pageComponents(GRAPH, "p1")).toEqual([
      { id: "c1", name: "Tlačítko výzvy", section: "cta", tech: "React", states: ["připraveno", "chyba"], out: [{ carries: "navigation", to: "Kontakt" }], in: [] },
    ]);
    expect(pageComponents(GRAPH, "p3").map((item) => item.id)).toEqual(["c3"]);
  });

  it("díry: stránka, její komponenty a hrany, přechody cesty se solverId stránky; ne podstránka, příchozí přechod ani shoda jen textem", () => {
    expect(pageHoles(CHECK, GRAPH, "p1", new Set(["j1"])).map((hole) => hole.rule)).toEqual(["journey.unrealized", "section.unrealized", "edge.carries-unset"]);
    expect(pageHoles(CHECK, GRAPH, "p1", new Set(["j1"]))[0].message).toContain("z /pestovani na /kontakt");
    expect(pageHoles(CHECK, GRAPH, "p1", new Set())).toHaveLength(2);
    expect(pageHoles(CHECK, GRAPH, "p3", new Set()).map((hole) => hole.rule)).toEqual(["state.no-error"]);
  });

  it("nenačtená kontrola mapy = holes null; uzel, který není stránka, nemá podklady", () => {
    expect(pageDecomposeFacts(GRAPH, "p1", null)?.holes).toBeNull();
    expect(pageDecomposeFacts(GRAPH, "c1", CHECK)).toBeNull();
    expect(pageDecomposeFacts(GRAPH, "chybi", CHECK)).toBeNull();
  });
});
