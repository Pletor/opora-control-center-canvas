import { describe, expect, it } from "vitest";
import { briefKey, briefView, missingText, statusText } from "./brief-model";
import { briefFixture } from "./brief-fixture";

describe("Výslech srdce: model panelu", () => {
  const view = briefView(briefFixture)!;

  it("syntéza čitelně: cíl, pro koho, části s původem, kritéria s ověřením, hranice", () => {
    expect(view.synthesis).toMatchObject({ goal: "Provozní metriky srdce pro člověka ve Velínu.", users: "člověk, který řídí projekt",
      outOfScope: ["export do Grafany"] });
    expect(view.synthesis!.parts.map(part => [part.text, part.originText, part.source])).toEqual([
      ["cena dávky", "od vás", null], ["chybovost dávek", "z rešerše", "https://sre.google/sre-book/"],
      ["doba do odpovědi", "odvozeno", "z ceny dávky"], ["divná", "původ neuveden", null]]);
    expect(view.synthesis!.acceptance.map(item => item.checkText)).toEqual(["ověří test", "ověří měření", null]);
  });

  it("otevřené otázky s doporučením a důvodem, zodpovězené zvlášť", () => {
    expect(view.open).toEqual([{ id: "q2", text: "Kdo to čte?", recommended: "Člověk ve Velínu.", why: "Určí rozsah." }]);
    expect(view.answered).toEqual([{ id: "q1", text: "Stačí denní trend?", answer: "Ano, denní.", accepted: true }]);
  });

  it("stav česky podle toho, zda srdce čeká na člověka", () => {
    expect([view.tone, view.statusText]).toEqual(["ask", "Srdce potřebuje vaši odpověď, než začne plánovat."]);
    expect(statusText("grilling", 0).text).toBe("Srdce zapracovává vaše odpovědi do pochopení.");
    expect(statusText("clear", 0).tone).toBe("clear");
    expect(statusText("draft", 0).tone).toBe("work");
  });

  it("co chybí: věty pro člověka bez technických klíčů, jasno nic", () => {
    expect(view.missing).toEqual(["hranice: co se dělat nebude", "aspoň jedna část z rešerše nebo odvozená, aby to nebyl jen přepis zadání",
      "vaše odpovědi na otázky výše"]);
    expect(missingText("goal: cíl jednou větou")).toBe("cíl jednou větou");
    expect(missingText("něco nového")).toBe("něco nového");
    expect(briefView({ ...briefFixture, status: "clear" })!.missing).toEqual([]);
  });

  it("spis bez syntézy a neplatný brief", () => {
    expect(briefView({ status: "draft", synthesis: null, questions: [], missing: [] })).toMatchObject({ synthesis: null, open: [], tone: "work" });
    expect(briefView(null)).toBeNull();
    expect(briefView({ questions: [] })).toBeNull();
  });
});

it("klíč zápisu: otázka požadavku, nebo spuštění výslechu", () => {
  expect(briefKey("rq_1", "q2")).toBe("brief:rq_1:q2");
  expect(briefKey("rq_1")).toBe("brief:rq_1");
});
