// Čistá pravidla klienta pro adresované zprávy: přesné payloady kontraktu, kontrola lokálního
// formuláře a slučování stránkovaného výpisu. Síť ani React sem nepatří.
export const MESSAGE_KINDS = ["handoff", "question", "answer", "blocker", "result", "correction"] as const;
export const RECEIPT_DISPOSITIONS = ["accepted", "rejected", "needs_clarification"] as const;
export const MAX_MESSAGE_BODY = 12000;
export const MAX_LABEL = 120;

export type MessageKind = (typeof MESSAGE_KINDS)[number];
export type ReceiptDisposition = (typeof RECEIPT_DISPOSITIONS)[number];
export type CommunicationScope = { project: string; workspace: string; nodeId: string };
export type MessageDraft = {
  targetNodeId: string; kind: MessageKind; body: string; replyToMessageId: string | null; senderLabel: string;
};
export type ReceiptDraft = { disposition: ReceiptDisposition; note: string; recipientLabel: string };
export type AgentMessage = {
  id: string; sequence: number; project: string; workspace: string; sourceNodeId: string; targetNodeId: string;
  kind: MessageKind; body: string; replyToMessageId: string | null; senderLabel: string; identityVerified: false;
  createdAt: string; digest: string;
  receipt: null | { disposition: ReceiptDisposition; note: string; recipientLabel: string; identityVerified: false; createdAt: string };
};

export type MessagePayload = Omit<MessageDraft, "targetNodeId"> & {
  project: string; workspace: string; sourceNodeId: string; targetNodeId: string; idempotencyKey: string;
};
export type ReceiptPayload = ReceiptDraft & {
  project: string; workspace: string; nodeId: string; messageId: string; digest: string;
};
type ImmutableReceipt = NonNullable<AgentMessage["receipt"]>;

const sameReceipt = (left: ImmutableReceipt, right: ImmutableReceipt): boolean =>
  left.disposition === right.disposition && left.note === right.note &&
  left.recipientLabel === right.recipientLabel && left.identityVerified === right.identityVerified &&
  left.createdAt === right.createdAt;

/** Ověří neměnnou verzi zprávy; u receipt navíc přesný serverový záznam i odeslané údaje. */
export function matchesMessageReadback(
  actual: AgentMessage, expected: AgentMessage, expectedReceipt?: ReceiptDraft,
): boolean {
  if (actual.id !== expected.id || actual.digest !== expected.digest) return false;
  if (!expectedReceipt) return true;
  if (!actual.receipt || !expected.receipt || !sameReceipt(actual.receipt, expected.receipt)) return false;
  if (actual.receipt.identityVerified !== false || expected.receipt.identityVerified !== false) return false;
  return actual.receipt.disposition === expectedReceipt.disposition &&
    actual.receipt.note === expectedReceipt.note && actual.receipt.recipientLabel === expectedReceipt.recipientLabel;
}

export const emptyMessageDraft = (): MessageDraft => ({
  targetNodeId: "", kind: "handoff", body: "", replyToMessageId: null, senderLabel: "",
});

/** Nastaví skutečnou protistranu a referenci vybrané příchozí zprávy, ale neničí rozepsaný text ani autora. */
export function replyDraft(draft: MessageDraft, message: Pick<AgentMessage, "id" | "sourceNodeId">): MessageDraft {
  return { ...draft, targetNodeId: message.sourceNodeId, kind: "answer", replyToMessageId: message.id };
}

const validText = (value: string, required: boolean): boolean =>
  value.length <= MAX_MESSAGE_BODY && !value.includes("\0") && (!required || value.trim().length > 0);
const validLabel = (value: string): boolean => value.length > 0 && value.length <= MAX_LABEL && !value.includes("\0");

/** Otisk přesně těch polí, které určují opakovatelný POST; změna vyžaduje nový idempotencyKey. */
export function draftFingerprint(draft: MessageDraft): string {
  return JSON.stringify([draft.targetNodeId, draft.kind, draft.body, draft.replyToMessageId, draft.senderLabel]);
}

export function canSendMessage(scope: CommunicationScope, draft: MessageDraft, readOnly: boolean): boolean {
  return !readOnly && draft.targetNodeId !== "" && draft.targetNodeId !== scope.nodeId &&
    validText(draft.body, true) && validLabel(draft.senderLabel);
}

export function canCreateReceipt(draft: ReceiptDraft, readOnly: boolean): boolean {
  const noteRequired = draft.disposition !== "accepted";
  return !readOnly && validLabel(draft.recipientLabel) && validText(draft.note, noteRequired);
}

export function makeMessagePayload(scope: CommunicationScope, draft: MessageDraft, idempotencyKey: string): MessagePayload {
  return {
    project: scope.project, workspace: scope.workspace, sourceNodeId: scope.nodeId,
    targetNodeId: draft.targetNodeId, kind: draft.kind, body: draft.body,
    replyToMessageId: draft.replyToMessageId, idempotencyKey, senderLabel: draft.senderLabel,
  };
}

export function makeReceiptPayload(
  scope: CommunicationScope, messageId: string, digest: string, draft: ReceiptDraft,
): ReceiptPayload {
  return {
    project: scope.project, workspace: scope.workspace, nodeId: scope.nodeId, messageId, digest,
    disposition: draft.disposition, note: draft.note, recipientLabel: draft.recipientLabel,
  };
}

/** Připojí další stránku bez duplicit; řazení vždy vrátí nejnovější serverové pořadí první. */
export function mergeMessagePage<T extends { id: string; sequence: number }>(existing: T[], next: T[]): T[] {
  const seen = new Set<string>();
  return [...existing, ...next]
    .filter((message) => !seen.has(message.id) && (seen.add(message.id), true))
    .sort((a, b) => b.sequence - a.sequence);
}

export type MessageDirection = "incoming" | "outgoing";
export type MessageStateKey = "saved" | ReceiptDisposition;
export type MessageState = { key: MessageStateKey; label: string };
/** Jedna rozprava kolem kořenové zprávy; odpovědi patří oběma směrům, protože vlákno je společné. */
export type MessageThread = {
  root: AgentMessage; replies: AgentMessage[]; direction: MessageDirection;
  superseded: boolean; supersededIds: string[]; pending: boolean; orphan: boolean;
};

export const MESSAGE_KIND_LABELS: Record<MessageKind, string> = {
  handoff: "Předávka", question: "Otázka", answer: "Odpověď", blocker: "Blokace", result: "Výsledek", correction: "Oprava",
};
export const RECEIPT_LABELS: Record<ReceiptDisposition, string> = {
  accepted: "Převzato", rejected: "Odmítnuto", needs_clarification: "Potřebuji upřesnění",
};
/** Slovesa akcí u zprávy; hlavička formuláře musí říct, co se právě chystám udělat, ne co už platí. */
export const RECEIPT_ACTION_LABELS: Record<ReceiptDisposition, string> = {
  accepted: "Převzít", rejected: "Odmítnout", needs_clarification: "Potřebuji upřesnění",
};
export const DIGEST_PREFIX = 12;
export const MAX_EXCERPT = 48;
const STATE_LABELS: Record<MessageStateKey, string> = {
  saved: "Uloženo, nepřevzato", accepted: "Převzato", rejected: "Odmítnuto", needs_clarification: "Vyžaduje upřesnění",
};

/** Verzi zprávy stačí poznat po předponě; celý digest zůstává v title atributu. */
export const shortDigest = (digest: string): string =>
  digest.length > DIGEST_PREFIX ? `${digest.slice(0, DIGEST_PREFIX)}…` : digest;

/** Jednořádkový výtah těla zprávy do hlavičky; víceřádkový text se srovná, delší se utne. */
export function messageExcerpt(body: string, limit = MAX_EXCERPT): string {
  const single = body.replace(/\s+/g, " ").trim();
  return single.length <= limit ? single : `${single.slice(0, limit).trimEnd()}…`;
}

/**
 * Hlavička formuláře převzetí: chystaná akce, typ zprávy, výtah těla a verze, ke které se
 * potvrzení váže. Formulář tak nikdy nevisí bez adresáta, i když je vláken na obrazovce víc.
 */
export function receiptHeadline(
  message: Pick<AgentMessage, "kind" | "body" | "digest">, disposition: ReceiptDisposition,
): string {
  return [
    RECEIPT_ACTION_LABELS[disposition], MESSAGE_KIND_LABELS[message.kind],
    messageExcerpt(message.body), `digest ${shortDigest(message.digest)}`,
  ].filter(Boolean).join(" · ");
}

/** Uložení na serveru není převzetí: bez potvrzení zpráva zůstává jen uložená. */
export function messageState(message: Pick<AgentMessage, "receipt">): MessageState {
  const key: MessageStateKey = message.receipt ? message.receipt.disposition : "saved";
  return { key, label: STATE_LABELS[key] };
}

export const directionOf = (message: Pick<AgentMessage, "targetNodeId">, nodeId: string): MessageDirection =>
  message.targetNodeId === nodeId ? "incoming" : "outgoing";

const olderFirst = (left: AgentMessage, right: AgentMessage): number =>
  left.sequence - right.sequence || (left.id < right.id ? -1 : left.id > right.id ? 1 : 0);
const indexById = (all: AgentMessage[]): Map<string, AgentMessage> =>
  new Map(all.map((message) => [message.id, message]));

/** Vystoupá po replyToMessageId na kořen; nenačtený nebo zacyklený rodič kořen ukončí. */
function rootMessage(index: Map<string, AgentMessage>, message: AgentMessage): AgentMessage {
  const seen = new Set<string>([message.id]);
  let current = message;
  for (;;) {
    const parentId = current.replyToMessageId;
    if (parentId === null || seen.has(parentId)) return current;
    const parent = index.get(parentId);
    if (!parent) return current;
    seen.add(parentId);
    current = parent;
  }
}

const isPending = (
  root: AgentMessage, replies: AgentMessage[], direction: MessageDirection, directions: Map<string, MessageDirection>,
): boolean => {
  // Cokoli příchozího bez potvrzení čeká na mě, ať je to kořen, nebo odpověď v mém vlákně.
  if (replies.some((reply) => directions.get(reply.id) === "incoming" && !reply.receipt)) return true;
  if (direction !== "incoming") return false;
  if (!root.receipt) return true;
  if (root.receipt.disposition !== "needs_clarification") return false;
  return !replies.some((reply) => directions.get(reply.id) === "outgoing" && reply.sequence > root.sequence);
};

/** Oba směry do jednoho seznamu vláken, nejnovější kořen první. Oprava nahrazuje odkazovanou zprávu. */
export function buildThreads(incoming: AgentMessage[], outgoing: AgentMessage[]): MessageThread[] {
  const directions = new Map<string, MessageDirection>();
  for (const message of outgoing) directions.set(message.id, "outgoing");
  for (const message of incoming) directions.set(message.id, "incoming");
  const seen = new Set<string>();
  const all = [...incoming, ...outgoing].filter((message) => !seen.has(message.id) && (seen.add(message.id), true));
  const index = indexById(all);
  const superseded = new Set<string>();
  for (const { kind, replyToMessageId } of all) {
    if (kind === "correction" && replyToMessageId !== null && index.has(replyToMessageId)) superseded.add(replyToMessageId);
  }
  const groups = new Map<string, { root: AgentMessage; members: AgentMessage[] }>();
  for (const message of all) {
    const root = rootMessage(index, message);
    const group = groups.get(root.id);
    if (group) group.members.push(message);
    else groups.set(root.id, { root, members: [message] });
  }
  return [...groups.values()]
    .map(({ root, members }) => {
      const replies = members.filter((message) => message.id !== root.id).sort(olderFirst);
      const direction = directions.get(root.id) ?? "incoming";
      return {
        root, replies, direction, superseded: superseded.has(root.id),
        supersededIds: [root, ...replies].map((message) => message.id).filter((id) => superseded.has(id)),
        pending: isPending(root, replies, direction, directions),
        orphan: root.replyToMessageId !== null && !index.has(root.replyToMessageId),
      };
    })
    .sort((left, right) => olderFirst(right.root, left.root));
}

export const pendingCount = (threads: MessageThread[]): number => threads.filter((thread) => thread.pending).length;

/** Popisek do shrnutí; nula mlčí, aby zavřený panel netvrdil, že je co vyřizovat. */
export function pendingSummary(count: number): string {
  if (count <= 0) return "";
  if (count === 1) return "1 nevyřízená";
  return `${count} ${count < 5 ? "nevyřízené" : "nevyřízených"}`;
}
