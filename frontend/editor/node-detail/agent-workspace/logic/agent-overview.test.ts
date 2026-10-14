import { describe, expect, it } from "vitest";
import { SECTIONS, emptyWorkspace, type AgentWorkspaceRecord } from "./agent-workspace";
import {
  READ_ONLY_TEXT,
  briefReadOnlyFlags,
  overviewModel,
  safetyLine,
  sectionIndicator,
  sectionsOpenByDefault,
} from "./agent-overview";

const options = { closed: false, mainReadOnly: false };

function workspaceRecord(overrides: Partial<AgentWorkspaceRecord> = {}): AgentWorkspaceRecord {
  return { ...emptyWorkspace(), ...overrides };
}

function message(overrides: Record<string, unknown> = {}) {
  return {
    id: "msg-1", sequence: 1, kind: "handoff", body: "Text zprávy", senderLabel: "agent",
    replyToMessageId: null, receipt: null, ...overrides,
  };
}

function brief(overrides: Record<string, unknown> = {}) {
  return {
    readOnly: false,
    loop: { done: { confirmed: false } },
    orientation: {
      scope: { nodeId: "focus", path: ["Sektor", "Ohnisko"], readOnly: false },
      goal: { goal: "Dodat UI", status: "present" },
      definitionOfDone: { acceptance: "Test je zelený.", blockConditions: [], status: "present" },
      contextGaps: [],
      nextAction: { kind: "follow-harness", label: "Pokračujte prvním nesplněným blokem karty." },
      safety: { readOnly: false, automaticModelInvocation: false, automaticAck: false, ownershipTransfer: false },
    },
    communication: {
      incoming: { messages: [], hasMore: false, nextBefore: null },
      outgoing: { messages: [], hasMore: false, nextBefore: null },
    },
    ...overrides,
  };
}

function withCommunication(incoming: unknown[], outgoing: unknown[] = [], extra: Record<string, unknown> = {}) {
  return brief({
    communication: {
      incoming: { messages: incoming, hasMore: false, nextBefore: null },
      outgoing: { messages: outgoing, hasMore: false, nextBefore: null },
      ...extra,
    },
  });
}

describe("agent-overview – prázdný a chybějící brief", () => {
  it("bez briefu nic nedomýšlí: prázdná cesta, nedostupná komunikace, chybějící ověření", () => {
    const model = overviewModel(null, emptyWorkspace(), options);
    expect(model.path).toEqual([]);
    expect(model.work).toEqual({ state: "empty", updatedAt: "", filled: 0, total: 5 });
    expect(model.communication).toEqual({
      available: false, awaitingReceipt: 0, needsClarification: 0, openQuestions: 0, hasMore: false,
    });
    expect(model.verification).toEqual({ goal: "missing", dod: "missing", gaps: 0 });
    expect(model.nextAction).toEqual({ label: "", kind: "" });
    expect(model.readOnlyReason).toBeNull();
  });

  it("pět sekcí prostoru zůstává pět; total přehledu je stejné číslo", () => {
    expect(SECTIONS.length).toBe(5);
    expect(overviewModel(null, emptyWorkspace(), options).work.total).toBe(SECTIONS.length);
  });

  it("z úplného briefu vezme cestu, cíl, definici hotovo a další krok doslova", () => {
    const model = overviewModel(brief(), emptyWorkspace(), options);
    expect(model.path).toEqual(["Sektor", "Ohnisko"]);
    expect(model.verification).toEqual({ goal: "present", dod: "present", gaps: 0 });
    expect(model.nextAction).toEqual({
      kind: "follow-harness", label: "Pokračujte prvním nesplněným blokem karty.",
    });
  });

  it("chybějící cíl a definice hotovo se počítají spolu s mezerami", () => {
    const value = brief({
      orientation: {
        ...brief().orientation,
        goal: { goal: "", status: "missing" },
        definitionOfDone: { acceptance: "", blockConditions: [], status: "missing" },
        contextGaps: [{ id: "goal", label: "Chybí cíl" }, { id: "acceptance", label: "Chybí definice hotovo" }],
      },
    });
    expect(overviewModel(value, emptyWorkspace(), options).verification).toEqual({
      goal: "missing", dod: "missing", gaps: 2,
    });
  });
});

describe("agent-overview – stav práce v pěti polích", () => {
  it("prázdný prostor je empty bez ohledu na to, kdo je zapsaný jako autor", () => {
    expect(overviewModel(brief(), workspaceRecord({ by: "agent" }), options).work.state).toBe("empty");
  });

  it("vyplněná pole se počítají a stav řekne, kdo psal naposled", () => {
    const record = workspaceRecord({ frame: "rámec", handoff: "předávka", by: "agent", updatedAt: "2026-09-16T08:00:00Z" });
    expect(overviewModel(brief(), record, options).work).toEqual({
      state: "agent", updatedAt: "2026-09-16T08:00:00Z", filled: 2, total: 5,
    });
  });

  it("bílé znaky nejsou obsah a člověk zůstává člověkem", () => {
    const record = workspaceRecord({ frame: "   \n", log: "postup", by: "human" });
    expect(overviewModel(brief(), record, options).work.state).toBe("human");
    expect(overviewModel(brief(), record, options).work.filled).toBe(1);
  });
});

describe("agent-overview – nevyřízené položky komunikace", () => {
  it("příchozí zpráva bez receiptu čeká na potvrzení", () => {
    const value = withCommunication([
      message({ id: "a" }),
      message({ id: "b", receipt: { disposition: "accepted", note: "", recipientLabel: "agent" } }),
    ]);
    const model = overviewModel(value, emptyWorkspace(), options);
    expect(model.communication.available).toBe(true);
    expect(model.communication.awaitingReceipt).toBe(1);
    expect(model.communication.needsClarification).toBe(0);
  });

  it("receipt needs_clarification se počítá zvlášť a už nečeká na potvrzení", () => {
    const value = withCommunication([
      message({ id: "a", receipt: { disposition: "needs_clarification", note: "Upřesni cíl", recipientLabel: "agent" } }),
      message({ id: "b", receipt: { disposition: "rejected", note: "Nepřebírám", recipientLabel: "agent" } }),
    ]);
    expect(overviewModel(value, emptyWorkspace(), options).communication).toEqual({
      available: true, awaitingReceipt: 0, needsClarification: 1, openQuestions: 0, hasMore: false,
    });
  });

  it("nezodpovězená otázka je otevřená, odpovězená už ne", () => {
    const unanswered = withCommunication([message({ id: "q1", kind: "question" })]);
    expect(overviewModel(unanswered, emptyWorkspace(), options).communication.openQuestions).toBe(1);

    const answered = withCommunication(
      [message({ id: "q1", kind: "question" })],
      [message({ id: "o1", kind: "answer", replyToMessageId: "q1" })],
    );
    expect(overviewModel(answered, emptyWorkspace(), options).communication.openQuestions).toBe(0);
  });

  it("odchozí odpověď na jinou otázku otevřenou otázku nezavírá", () => {
    const value = withCommunication(
      [message({ id: "q1", kind: "question" }), message({ id: "q2", kind: "question" })],
      [message({ id: "o1", kind: "answer", replyToMessageId: "q2" })],
    );
    expect(overviewModel(value, emptyWorkspace(), options).communication.openQuestions).toBe(1);
  });

  it("stránkování hlásí, že starší zprávy zůstávají mimo načtený brief", () => {
    const value = brief({
      communication: {
        incoming: { messages: [message()], hasMore: true, nextBefore: "10" },
        outgoing: { messages: [], hasMore: false, nextBefore: null },
      },
    });
    expect(overviewModel(value, emptyWorkspace(), options).communication.hasMore).toBe(true);
  });

  it("nedostupná komunikace nemá počty; nula zpráv naopak dostupná zůstává", () => {
    const down = withCommunication([message()], [], { status: "unavailable", reason: "MessageStore nebyl připojen." });
    expect(overviewModel(down, emptyWorkspace(), options).communication).toEqual({
      available: false, awaitingReceipt: 0, needsClarification: 0, openQuestions: 0, hasMore: false,
    });
    const empty = overviewModel(brief(), emptyWorkspace(), options).communication;
    expect(empty.available).toBe(true);
    expect(empty.awaitingReceipt).toBe(0);
  });

  it("chybějící sekce communication je nedostupnost, ne prázdná historie", () => {
    const value = brief({ communication: undefined });
    expect(overviewModel(value, emptyWorkspace(), options).communication.available).toBe(false);
  });
});

describe("agent-overview – bezpečnostní záruky", () => {
  it("brief s false znamená záruku a skládá přesnou větu", () => {
    const model = overviewModel(brief(), emptyWorkspace(), options);
    expect(model.safety).toEqual({ modelInvocation: false, automaticAck: false, ownershipTransfer: false });
    expect(safetyLine(model.safety)).toBe(
      "Aplikace model nespouští, převzetí nepotvrzuje automaticky, vlastnictví nepřevádí.",
    );
  });

  it("chybějící pole není záruka: hlásí se jako neuvedeno", () => {
    const value = brief({ orientation: { ...brief().orientation, safety: { automaticAck: false } } });
    const model = overviewModel(value, emptyWorkspace(), options);
    expect(model.safety).toEqual({ modelInvocation: null, automaticAck: false, ownershipTransfer: null });
    expect(safetyLine(model.safety)).toBe(
      "Aplikace převzetí nepotvrzuje automaticky. Neuvedeno: spouštění modelu, převod vlastnictví.",
    );
  });

  it("úplně chybějící safety nehlásí žádnou záruku", () => {
    const value = brief({ orientation: { ...brief().orientation, safety: undefined } });
    const model = overviewModel(value, emptyWorkspace(), options);
    expect(model.safety).toEqual({ modelInvocation: null, automaticAck: null, ownershipTransfer: null });
    expect(safetyLine(model.safety)).toBe(
      "Neuvedeno: spouštění modelu, automatické potvrzení převzetí, převod vlastnictví.",
    );
  });

  it("true v briefu se neschovává za uklidňující větu", () => {
    const value = brief({
      orientation: {
        ...brief().orientation,
        safety: { automaticModelInvocation: false, automaticAck: true, ownershipTransfer: false },
      },
    });
    expect(safetyLine(overviewModel(value, emptyWorkspace(), options).safety)).toBe(
      "Aplikace model nespouští, vlastnictví nepřevádí. Brief hlásí: převzetí potvrzuje automaticky.",
    );
  });
});

describe("agent-overview – proč je zápis zamčený", () => {
  it("otevřená karta s právem zápisu nemá důvod", () => {
    expect(overviewModel(brief(), emptyWorkspace(), options).readOnlyReason).toBeNull();
  });

  it("uzavřená karta má vlastní větu a přebíjí main", () => {
    const model = overviewModel(brief(), emptyWorkspace(), { closed: true, mainReadOnly: true });
    expect(model.readOnlyReason).toBe("closed");
    expect(READ_ONLY_TEXT.closed).toBe("Karta je uzavřená: paměť a zprávy jsou jen ke čtení.");
  });

  it("main bez zápisu má svou vlastní větu", () => {
    const model = overviewModel(brief(), emptyWorkspace(), { closed: false, mainReadOnly: true });
    expect(model.readOnlyReason).toBe("main");
    expect(READ_ONLY_TEXT.main).toBe("Main je jen ke čtení; pracuj v pracovním prostoru.");
  });

  it("briefReadOnlyFlags čte důvod z autoritativního briefu, ne z dohadu", () => {
    expect(briefReadOnlyFlags(brief())).toEqual({ closed: false, mainReadOnly: false });
    expect(briefReadOnlyFlags(brief({ loop: { done: { confirmed: true } } }))).toEqual({
      closed: true, mainReadOnly: false,
    });
    expect(briefReadOnlyFlags(brief({ readOnly: true }))).toEqual({ closed: false, mainReadOnly: true });
    expect(briefReadOnlyFlags(null)).toEqual({ closed: false, mainReadOnly: false });
  });
});

describe("agent-overview – skládání pěti sekcí", () => {
  it("prázdná sekce je označená slovem, vyplněná počtem znaků", () => {
    expect(sectionIndicator("")).toBe("prázdné");
    expect(sectionIndicator("   ")).toBe("prázdné");
    expect(sectionIndicator("abc")).toBe("3 znaky");
    expect(sectionIndicator("a")).toBe("1 znak");
    expect(sectionIndicator("a".repeat(12))).toBe("12 znaků");
  });

  it("sekce s obsahem začínají otevřené, prázdné zavřené", () => {
    expect(sectionsOpenByDefault(workspaceRecord({ frame: "rámec", fixes: "oprava" }))).toEqual({
      frame: true, log: false, failures: false, fixes: true, handoff: false,
    });
    expect(sectionsOpenByDefault(emptyWorkspace())).toEqual({
      frame: false, log: false, failures: false, fixes: false, handoff: false,
    });
  });
});
