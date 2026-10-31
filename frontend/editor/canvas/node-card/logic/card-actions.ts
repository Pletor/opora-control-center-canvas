// Akce karet přes kontext (docs/navrhy/2026-10-14-vykon-platna.md, oprava 3). Karta dřív dostávala
// v `data` asi dvacet nových closures při každé přestavbě, takže `memo` nic nechránilo. Teď Board
// předá jeden stabilní objekt akcí a karta volá `actions.cardBlock(id, event)`. Akce jen bublají nahoru
// (do Boardu a odtud do App); nic neukládají a nic nečtou ze stavu karty.
import { createContext, useContext } from "react";
import type { Rule } from "@/shared/desktop-state/logic/types";
import type { RuleReviewDecision } from "@/shared/desktop-state/logic/agent-rule";
import type { BlockPort } from "@/editor/canvas/node-card/components/CardPorts";

/** Změna bloku nebo portu v kartě; tvar sdílí Board (`CardBlockEvent`) i App. */
export type CardBlockEvent =
  | { type: "add" }
  | { type: "move"; blockId: string; delta: -1 | 1 }
  | { type: "remove"; blockId: string }
  | { type: "rename"; blockId: string; title: string }
  | { type: "text"; blockId: string; text: string }
  | { type: "add-port"; blockId: string }
  | { type: "rename-port"; blockId: string; portId: string; label: string }
  | { type: "remove-port"; blockId: string; portId: string }
  | { type: "decide-port"; blockId: string; portId: string; status: "chosen" | "rejected" | ""; reason: string };

export type CardActions = {
  open: (id: string) => void;
  /** Klik na poslední změnu karty: otevřít záznam činnosti s filtrem „Jen vybraná karta“. */
  history: (id: string) => void;
  /** Klik na postup na tváři karty: otevřít boční menu se stopou práce karty (i bez bloku). */
  trail: (id: string) => void;
  tag: (tag: string) => void;
  renameStart: (id: string) => void;
  renameCancel: (id: string) => void;
  renameCommit: (id: string, name: string) => void;
  /** Přejmenování komentáře nebo oblasti (titulek už ořízlý a jiný než uložený). */
  renameNode: (id: string, name: string) => void;
  commentText: (id: string, text: string) => void;
  resizeArea: (id: string, w: number, h: number) => void;
  togglePort: (id: string, port: BlockPort) => void;
  cardBlock: (id: string, event: CardBlockEvent) => void;
  confirm: (id: string) => Promise<boolean>;
  realize: (id: string, commit: string, prUrl: string) => Promise<void>;
  releaseLease: (id: string) => Promise<unknown>;
  ruleWrite: (expected: Rule, item: Rule) => Promise<boolean>;
  ruleReview: (rule: Rule, decision: RuleReviewDecision) => Promise<boolean>;
};

const idle = () => {};
const no = async () => false;
/** Výchozí akce mimo Board (testy, náhled): nic se nestane a nic se neuloží. */
export const NO_CARD_ACTIONS: CardActions = {
  open: idle, history: idle, trail: idle, tag: idle, renameStart: idle, renameCancel: idle, renameCommit: idle, renameNode: idle,
  commentText: idle, resizeArea: idle, togglePort: idle, cardBlock: idle, confirm: no,
  realize: async () => {}, releaseLease: async () => undefined, ruleWrite: no, ruleReview: no,
};

export const CardActionsContext = createContext<CardActions>(NO_CARD_ACTIONS);
export const useCardActions = () => useContext(CardActionsContext);
