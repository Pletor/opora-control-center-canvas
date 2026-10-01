import { describe, expect, it } from "vitest";
import {
  MAX_MESSAGE_BODY,
  buildThreads,
  canCreateReceipt,
  canSendMessage,
  directionOf,
  draftFingerprint,
  makeMessagePayload,
  makeReceiptPayload,
  matchesMessageReadback,
  mergeMessagePage,
  messageExcerpt,
  messageState,
  pendingCount,
  pendingSummary,
  receiptHeadline,
  replyDraft,
  shortDigest,
  type AgentMessage,
  type MessageDraft,
  type ReceiptDraft,
} from "./agent-communication";

const scope = { project: "project-a", workspace: "branch-a", nodeId: "node-a" };
const draft: MessageDraft = {
  targetNodeId: "node-b",
  kind: "question",
  body: "Je rozhraní připravené?",
  replyToMessageId: null,
  senderLabel: "Dana · frontend",
};

describe("agent-communication", () => {
  it("vytvoří payload zprávy přesně podle kontraktu včetně null replyToMessageId", () => {
    expect(makeMessagePayload(scope, draft, "retry-key")).toEqual({
      project: "project-a",
      workspace: "branch-a",
      sourceNodeId: "node-a",
      targetNodeId: "node-b",
      kind: "question",
      body: "Je rozhraní připravené?",
      replyToMessageId: null,
      idempotencyKey: "retry-key",
      senderLabel: "Dana · frontend",
    });
  });

  it("otisk draftu je stejný při nezměněném retry a změní se při změně obsahu", () => {
    expect(draftFingerprint(draft)).toBe(draftFingerprint({ ...draft }));
    expect(draftFingerprint({ ...draft, body: "Jiná otázka" })).not.toBe(draftFingerprint(draft));
  });

  it("odeslání zablokuje na read-only, cíli u sebe, prázdném nebo NUL textu", () => {
    expect(canSendMessage(scope, draft, false)).toBe(true);
    expect(canSendMessage(scope, draft, true)).toBe(false);
    expect(canSendMessage(scope, { ...draft, targetNodeId: "node-a" }, false)).toBe(false);
    expect(canSendMessage(scope, { ...draft, body: "   " }, false)).toBe(false);
    expect(canSendMessage(scope, { ...draft, body: "a\0b" }, false)).toBe(false);
    expect(canSendMessage(scope, { ...draft, body: "a".repeat(MAX_MESSAGE_BODY + 1) }, false)).toBe(false);
  });

  it("vytvoří payload převzetí přesně podle kontraktu", () => {
    const receipt: ReceiptDraft = {
      disposition: "needs_clarification",
      note: "Prosím doplnit rozsah.",
      recipientLabel: "Marek · backend",
    };
    expect(makeReceiptPayload(scope, "message-1", "a".repeat(64), receipt)).toEqual({
      project: "project-a",
      workspace: "branch-a",
      nodeId: "node-a",
      messageId: "message-1",
      digest: "a".repeat(64),
      disposition: "needs_clarification",
      note: "Prosím doplnit rozsah.",
      recipientLabel: "Marek · backend",
    });
  });

  it("odmítnutí a žádost o upřesnění bez poznámky nepovolí, ale přijetí ano", () => {
    expect(canCreateReceipt({ disposition: "accepted", note: "", recipientLabel: "Dana" }, false)).toBe(true);
    expect(canCreateReceipt({ disposition: "rejected", note: "", recipientLabel: "Dana" }, false)).toBe(false);
    expect(canCreateReceipt({ disposition: "needs_clarification", note: "", recipientLabel: "Dana" }, false)).toBe(false);
  });

  it("readback vyžaduje přesný digest i všechny údaje neměnného potvrzení", () => {
    const expected = {
      id: "message-1", sequence: 5, project: "project-a", workspace: "branch-a", sourceNodeId: "node-b", targetNodeId: "node-a",
      kind: "question" as const, body: "Je to hotové?", replyToMessageId: null, senderLabel: "Marek", identityVerified: false as const,
      createdAt: "2026-09-16T10:00:00Z", digest: "a".repeat(64),
      receipt: { disposition: "accepted" as const, note: "", recipientLabel: "Dana", identityVerified: false as const, createdAt: "2026-09-16T10:01:00Z" },
    };
    const receipt: ReceiptDraft = { disposition: "accepted", note: "", recipientLabel: "Dana" };
    expect(matchesMessageReadback(expected, expected, receipt)).toBe(true);
    expect(matchesMessageReadback({ ...expected, digest: "b".repeat(64) }, expected, receipt)).toBe(false);
    expect(matchesMessageReadback({ ...expected, receipt: { ...expected.receipt, note: "jiná" } }, expected, receipt)).toBe(false);
    expect(matchesMessageReadback({ ...expected, receipt: { ...expected.receipt, createdAt: "2026-09-16T10:02:00Z" } }, expected, receipt)).toBe(false);
  });

  it("stránku zpráv připojí bez duplicit a zachová nejnovější první", () => {
    const existing = [{ id: "m3", sequence: 3 }, { id: "m2", sequence: 2 }];
    const next = [{ id: "m2", sequence: 2 }, { id: "m1", sequence: 1 }];
    expect(mergeMessagePage(existing, next)).toEqual([
      { id: "m3", sequence: 3 },
      { id: "m2", sequence: 2 },
      { id: "m1", sequence: 1 },
    ]);
  });

  it("odpověď předvyplní protistranu, referenci a typ answer bez smazání rozepsaného textu", () => {
    expect(replyDraft({ ...draft, body: "Hotové rozhraní." }, { id: "message-7", sourceNodeId: "node-b" })).toEqual({
      ...draft, targetNodeId: "node-b", kind: "answer", replyToMessageId: "message-7", body: "Hotové rozhraní.",
    });
  });
});

/** Zpráva z pohledu karty node-a: příchozí má cíl node-a, odchozí zdroj node-a. */
const incomingMessage = (over: Partial<AgentMessage> & { id: string; sequence: number }): AgentMessage => ({
  project: "project-a", workspace: "branch-a", sourceNodeId: "node-b", targetNodeId: "node-a",
  kind: "handoff", body: "Předávám rozhraní.", replyToMessageId: null, senderLabel: "Marek · backend",
  identityVerified: false, createdAt: "2026-09-16T10:00:00Z", digest: "a".repeat(64), receipt: null,
  ...over,
});
const outgoingMessage = (over: Partial<AgentMessage> & { id: string; sequence: number }): AgentMessage =>
  incomingMessage({ sourceNodeId: "node-a", targetNodeId: "node-b", senderLabel: "Dana · frontend", ...over });
const accepted = (createdAt = "2026-09-16T10:05:00Z") =>
  ({ disposition: "accepted" as const, note: "", recipientLabel: "Dana", identityVerified: false as const, createdAt });
const clarification = (createdAt = "2026-09-16T10:05:00Z") =>
  ({ disposition: "needs_clarification" as const, note: "Chybí rozsah.", recipientLabel: "Dana", identityVerified: false as const, createdAt });

describe("agent-communication: stav zprávy", () => {
  it("bez potvrzení hlásí uloženo, s potvrzením přesnou dispozici", () => {
    expect(messageState(incomingMessage({ id: "m1", sequence: 1 }))).toEqual({ key: "saved", label: "Uloženo, nepřevzato" });
    expect(messageState(incomingMessage({ id: "m1", sequence: 1, receipt: accepted() })))
      .toEqual({ key: "accepted", label: "Převzato" });
    expect(messageState(incomingMessage({ id: "m1", sequence: 1, receipt: { ...accepted(), disposition: "rejected", note: "Mimo rozsah." } })))
      .toEqual({ key: "rejected", label: "Odmítnuto" });
    expect(messageState(incomingMessage({ id: "m1", sequence: 1, receipt: clarification() })))
      .toEqual({ key: "needs_clarification", label: "Vyžaduje upřesnění" });
  });

  it("směr zprávy čte z pohledu vlastní karty", () => {
    expect(directionOf(incomingMessage({ id: "m1", sequence: 1 }), "node-a")).toBe("incoming");
    expect(directionOf(outgoingMessage({ id: "m2", sequence: 2 }), "node-a")).toBe("outgoing");
  });
});

describe("agent-communication: vlákna", () => {
  it("odpověď připojí ke kořeni i přes změnu směru a seřadí je chronologicky", () => {
    const root = incomingMessage({ id: "m1", sequence: 1 });
    const answer = outgoingMessage({ id: "m2", sequence: 2, kind: "answer", replyToMessageId: "m1" });
    const followUp = incomingMessage({ id: "m3", sequence: 3, kind: "question", replyToMessageId: "m2" });
    const threads = buildThreads([root, followUp], [answer]);
    expect(threads).toHaveLength(1);
    expect(threads[0].direction).toBe("incoming");
    expect(threads[0].replies.map((message) => message.id)).toEqual(["m2", "m3"]);
  });

  it("oprava označí odkazovanou zprávu jako nahrazenou", () => {
    const root = incomingMessage({ id: "m1", sequence: 1 });
    const fix = incomingMessage({ id: "m2", sequence: 2, kind: "correction", replyToMessageId: "m1" });
    const [thread] = buildThreads([root, fix], []);
    expect(thread.superseded).toBe(true);
    expect(thread.supersededIds).toEqual(["m1"]);

    const plain = buildThreads([root, incomingMessage({ id: "m3", sequence: 3, kind: "answer", replyToMessageId: "m1" })], []);
    expect(plain[0].superseded).toBe(false);
    expect(plain[0].supersededIds).toEqual([]);
  });

  it("nevyřízené je příchozí vlákno bez potvrzení nebo s upřesněním bez vlastní odpovědi", () => {
    const open = buildThreads([incomingMessage({ id: "m1", sequence: 1 })], []);
    expect(open[0].pending).toBe(true);

    const done = buildThreads([incomingMessage({ id: "m1", sequence: 1, receipt: accepted() })], []);
    expect(done[0].pending).toBe(false);

    const refused = buildThreads([incomingMessage({ id: "m1", sequence: 1, receipt: { ...accepted(), disposition: "rejected", note: "Mimo rozsah." } })], []);
    expect(refused[0].pending).toBe(false);

    const asked = buildThreads([incomingMessage({ id: "m1", sequence: 1, receipt: clarification() })], []);
    expect(asked[0].pending).toBe(true);

    const answeredRoot = incomingMessage({ id: "m1", sequence: 1, receipt: clarification() });
    const answered = buildThreads([answeredRoot], [outgoingMessage({ id: "m2", sequence: 2, kind: "question", replyToMessageId: "m1" })]);
    expect(answered[0].pending).toBe(false);

    const mine = buildThreads([], [outgoingMessage({ id: "m9", sequence: 9 })]);
    expect(mine[0].direction).toBe("outgoing");
    expect(mine[0].pending).toBe(false);

    // Příchozí odpověď bez potvrzení uvnitř mého vlákna čeká na mě stejně jako kořen.
    const replied = buildThreads(
      [incomingMessage({ id: "m10", sequence: 10, kind: "answer", replyToMessageId: "m9" })],
      [outgoingMessage({ id: "m9", sequence: 9 })],
    );
    expect(replied[0].pending).toBe(true);
    const repliedAck = buildThreads(
      [incomingMessage({ id: "m10", sequence: 10, kind: "answer", replyToMessageId: "m9", receipt: accepted() })],
      [outgoingMessage({ id: "m9", sequence: 9 })],
    );
    expect(repliedAck[0].pending).toBe(false);
  });

  it("odpověď na nenačtenou zprávu stojí jako vlastní kořen s příznakem chybějícího originálu", () => {
    const orphan = incomingMessage({ id: "m5", sequence: 5, kind: "answer", replyToMessageId: "m0" });
    const own = outgoingMessage({ id: "m6", sequence: 6 });
    const threads = buildThreads([orphan], [own]);
    expect(threads.map((thread) => [thread.root.id, thread.orphan])).toEqual([["m6", false], ["m5", true]]);
  });

  it("vlákna řadí nejnovější kořen první a počítá nevyřízená", () => {
    const first = incomingMessage({ id: "m1", sequence: 1, receipt: accepted() });
    const second = outgoingMessage({ id: "m2", sequence: 2 });
    const third = incomingMessage({ id: "m3", sequence: 3 });
    const reply = outgoingMessage({ id: "m4", sequence: 4, kind: "answer", replyToMessageId: "m1" });
    const threads = buildThreads([first, third], [second, reply]);
    expect(threads.map((thread) => thread.root.id)).toEqual(["m3", "m2", "m1"]);
    expect(threads).toEqual(buildThreads([third, first], [reply, second]));
    expect(pendingCount(threads)).toBe(1);
    expect(pendingCount(buildThreads([], []))).toBe(0);
  });

  it("souhrn nevyřízených skloňuje a při nule mlčí", () => {
    expect(pendingSummary(0)).toBe("");
    expect(pendingSummary(1)).toBe("1 nevyřízená");
    expect(pendingSummary(2)).toBe("2 nevyřízené");
    expect(pendingSummary(5)).toBe("5 nevyřízených");
  });
});

describe("agent-communication: hlavička potvrzení", () => {
  it("digest zkrátí na čitelnou předponu a kratší nechá celý", () => {
    expect(shortDigest("7cce2d95ab12cd34")).toBe("7cce2d95ab12…");
    expect(shortDigest("7cce2d95")).toBe("7cce2d95");
    expect(shortDigest("")).toBe("");
  });

  it("výtah zprávy je jeden řádek a delší text končí výpustkou", () => {
    expect(messageExcerpt("Krátká zpráva.")).toBe("Krátká zpráva.");
    expect(messageExcerpt("První řádek\n\n  druhý řádek  ")).toBe("První řádek druhý řádek");
    expect(messageExcerpt("a".repeat(60))).toBe(`${"a".repeat(48)}…`);
    expect(messageExcerpt("   ")).toBe("");
  });

  it("hlavička pojmenuje akci, typ, výtah zprávy i její verzi", () => {
    const message = incomingMessage({
      id: "m1", sequence: 1, kind: "question",
      body: "UX test: který formát chceš?", digest: `7cce2d95${"f".repeat(56)}`,
    });
    expect(receiptHeadline(message, "accepted"))
      .toBe("Převzít · Otázka · UX test: který formát chceš? · digest 7cce2d95ffff…");
    expect(receiptHeadline(message, "rejected"))
      .toBe("Odmítnout · Otázka · UX test: který formát chceš? · digest 7cce2d95ffff…");
    expect(receiptHeadline(message, "needs_clarification"))
      .toBe("Potřebuji upřesnění · Otázka · UX test: který formát chceš? · digest 7cce2d95ffff…");
  });

  it("prázdné tělo hlavičku nerozbije, jen v ní mlčí", () => {
    const message = incomingMessage({ id: "m2", sequence: 2, body: "   ", digest: "abc" });
    expect(receiptHeadline(message, "accepted")).toBe("Převzít · Předávka · digest abc");
  });
});
