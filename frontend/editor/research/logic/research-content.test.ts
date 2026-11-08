import { expect, it } from "vitest";
import { researchContent } from "./research-content";

it("recognizes imported facts without truncating quotes or project relevance", () => {
  const quote = "Dlouhý doklad. ".repeat(5000);
  expect(researchContent(JSON.stringify({ id: "f1", kind: "fact", claim: "Jedna relace, jeden tenant", quote, relevance: "Izolace projektu", unknown: { keep: true } }))).toEqual([
    { label: "Tvrzení", text: "Jedna relace, jeden tenant" }, { label: "Význam pro projekt", text: "Izolace projektu" }, { label: "Citovaná pasáž", text: quote },
  ]);
});
it("renders comparison arguments and hypotheses as readable fields", () => {
  const fields = researchContent(JSON.stringify({ option: { approach: "OIDC", pros: ["Standard", "SSO"], cons: "Závislost na poskytovateli" }, risks: ["Výpadek"], hypotheses: [{ claim: "IdP je dostupný", check: "Ověřit smlouvu" }], approval: "Návrh" }));
  expect(fields).toContainEqual({ label: "Výhody", text: "Standard\nSSO" });
  expect(fields).toContainEqual({ label: "Způsob ověření", text: "Ověřit smlouvu" });
});
it("leaves prose, malformed JSON and unrelated JSON in their original presentation", () => {
  for (const input of ["Obyčejný text", "{broken", '["text"]', '{"claim":"unrelated"}', '{"option":{"approach":42}}']) expect(researchContent(input)).toBeNull();
});
