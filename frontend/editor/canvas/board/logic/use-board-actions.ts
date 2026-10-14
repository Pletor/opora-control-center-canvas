// Jeden stabilní objekt akcí karet pro celý Board (docs/navrhy/2026-10-14-vykon-platna.md, oprava 3).
// Objekt vzniká jednou za život Boardu a každá akce čte poslední props přes ref, takže karta nikdy nedrží
// zastaralý callback, a přesto se kvůli novým closures v App nemusí překreslit. Akce jen bublají nahoru.
import { useLayoutEffect, useMemo, useRef } from "react";
import type { CardActions, CardBlockEvent } from "@/editor/canvas/node-card/logic/card-actions";
import type { BlockPort } from "@/editor/canvas/node-card/components/CardPorts";
import type { CompletionEvidence } from "@/editor/canvas/node-card/components/CardEvidence";
import type { Rule } from "@/shared/desktop-state/logic/types";
import type { RuleReviewDecision } from "@/shared/desktop-state/logic/agent-rule";
import { releaseLease } from "@/editor/canvas/node-card/logic/release-lease";

export type BoardActionProps = {
  disabled: boolean;
  /** Uložené jméno uzlu; přejmenování stejným jménem se nehlásí. */
  nameOf: (id: string) => string | undefined;
  onSelect: (id: string) => void;
  onTagFilter: (tag: string) => void;
  onEditing: (id: string | null) => void;
  onRename: (id: string, name: string) => void;
  onCommentText: (id: string, text: string) => void;
  onAreaResize: (id: string, w: number, h: number) => void;
  onTogglePort: (nodeId: string, port: BlockPort) => void;
  onCardBlock: (nodeId: string, event: CardBlockEvent) => void;
  onSaveEvidence?: (nodeId: string, value: CompletionEvidence) => Promise<boolean>;
  onConfirmProposal?: (nodeId: string) => Promise<boolean>;
  onUrlDownload?: (nodeId: string, enabled: boolean) => Promise<boolean>;
  onRealizeSource?: (nodeId: string, commit: string, prUrl: string) => Promise<void>;
  onRuleWrite?: (expected: Rule, item: Rule) => Promise<boolean>;
  onRuleReview?: (rule: Rule, decision: RuleReviewDecision) => Promise<boolean>;
  sourceContext?: { project: string; workspace: string };
};

export function useBoardActions(props: BoardActionProps): CardActions {
  // Jen potvrzené props: render, který React zahodí (souběžné vykreslování), akce nepřepíše.
  const latest = useRef(props);
  useLayoutEffect(() => { latest.current = props; });
  return useMemo<CardActions>(() => ({
    open: (id) => latest.current.onSelect(id),
    tag: (tag) => latest.current.onTagFilter(tag),
    renameStart: (id) => { if (!latest.current.disabled) latest.current.onEditing(id); },
    renameCancel: () => latest.current.onEditing(null),
    renameCommit: (id, name) => {
      const { onEditing, onRename, nameOf } = latest.current;
      onEditing(null);
      const next = name.trim();
      if (next && next !== nameOf(id)) onRename(id, next);
    },
    renameNode: (id, name) => latest.current.onRename(id, name),
    commentText: (id, text) => latest.current.onCommentText(id, text),
    resizeArea: (id, w, h) => latest.current.onAreaResize(id, w, h),
    togglePort: (id, port) => { if (!latest.current.disabled) latest.current.onTogglePort(id, port); },
    cardBlock: (id, event) => latest.current.onCardBlock(id, event),
    saveEvidence: (id, value) => latest.current.onSaveEvidence?.(id, value) ?? Promise.resolve(false),
    confirm: (id) => latest.current.onConfirmProposal?.(id) ?? Promise.resolve(false),
    urlDownload: (id, enabled) => latest.current.onUrlDownload?.(id, enabled) ?? Promise.resolve(false),
    realize: (id, commit, prUrl) => latest.current.onRealizeSource?.(id, commit, prUrl) ?? Promise.resolve(),
    releaseLease: (id) => {
      const scope = latest.current.sourceContext;
      return scope ? releaseLease(scope.project, scope.workspace, id) : Promise.resolve(undefined);
    },
    ruleWrite: (expected, item) => latest.current.onRuleWrite?.(expected, item) ?? Promise.resolve(false),
    ruleReview: (rule, decision) => latest.current.onRuleReview?.(rule, decision) ?? Promise.resolve(false),
  }), []);
}
