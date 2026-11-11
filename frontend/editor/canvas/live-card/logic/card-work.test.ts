import { describe, expect, it } from "vitest";
import { LIVE_CARD_BARE, LIVE_CARD_FULL } from "./live-card-fixture";
import { workBody, workDraft } from "./card-work";

describe("workDraft", () => {
  it("předvyplní název, záměr s cestou a kritéria z vize", () => {
    expect(workDraft(LIVE_CARD_FULL)).toEqual({
      title: "Přijmout platbu",
      essence: "Prodej kurzu › M2 Lze zaplatit › Přijmout platbu: doplnit member_id do payment.paid",
      build: "doplnit member_id do payment.paid",
      doneCriteria: "Platba přes FAPI\nNeplatný podpis = 401",
    });
  });
  it("holá karta: jen název, ostatní prázdné", () => {
    expect(workDraft(LIVE_CARD_BARE)).toEqual({ title: "Potvrzovací e-mail", essence: "Potvrzovací e-mail", build: "", doneCriteria: "" });
  });
});

describe("workBody", () => {
  it("přidá cardId k tělu formuláře", () => {
    expect(workBody({ title: "A", doneCriteria: ["x"] }, "pay")).toEqual({ title: "A", doneCriteria: ["x"], cardId: "pay" });
  });
});
