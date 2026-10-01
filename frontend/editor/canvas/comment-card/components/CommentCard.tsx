// Komentář na plátně: lepicí lístek, ne karta uzlu — beze portů, bez bloků, dvojklik do hloubky ho neotvírá.
// Rodič (Board) dodá hotová data; přejmenování titulku a změna textu bublají nahoru přes onRename / onText.
import { memo, useEffect, useRef, useState } from "react";
import type { Node, NodeProps } from "@xyflow/react";
import type { CommentView } from "@/editor/canvas/comment-card/logic/comment-model";
import "@/editor/canvas/comment-card/styles/comment-card.css";

export type CommentCardData = {
  view: CommentView;
  disabled: boolean;
  onRename: (title: string) => void;
  onText: (text: string) => void;
};

const CommentCard = memo(function CommentCard({ id, data, selected }: NodeProps<Node<CommentCardData>>) {
  const { view, disabled, onRename, onText } = data;
  const [editing, setEditing] = useState(false);
  const titleField = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!editing) return;
    titleField.current?.focus();
    titleField.current?.select();
  }, [editing]);

  const commitTitle = (value: string) => {
    setEditing(false);
    const next = value.trim();
    if (next && next !== view.title) onRename(next);
  };

  return (
    <div
      className={"comment-card" + (selected ? " comment-card--selected" : "")}
      data-testid={"comment-card-" + id}
    >
      <div className="comment-card__eyebrow">✎ komentář</div>
      {editing ? (
        <input
          ref={titleField}
          className="nodrag comment-card__title-input"
          aria-label="Název komentáře"
          data-testid={"comment-rename-" + id}
          defaultValue={view.title}
          autoFocus
          maxLength={160}
          onFocus={(e) => e.currentTarget.select()}
          onKeyDown={(e) => {
            e.stopPropagation();
            if (e.nativeEvent.isComposing) return;
            if (e.key === "Enter") commitTitle(e.currentTarget.value);
            if (e.key === "Escape") setEditing(false);
          }}
          onBlur={(e) => commitTitle(e.currentTarget.value)}
        />
      ) : (
        <h3
          className="comment-card__title"
          title={disabled ? view.title : "Dvojklik přejmenuje komentář"}
          onDoubleClick={(e) => {
            e.stopPropagation();
            if (!disabled) setEditing(true);
          }}
        >
          {view.title}
        </h3>
      )}
      <textarea
        className="nodrag comment-card__text"
        aria-label="Text komentáře"
        data-testid={"comment-text-" + id}
        placeholder="Poznámka…"
        defaultValue={view.text}
        readOnly={disabled}
        onKeyDown={(e) => e.stopPropagation()}
        onDoubleClick={(e) => e.stopPropagation()}
        onBlur={(e) => {
          const next = e.currentTarget.value;
          if (next !== view.text) onText(next);
        }}
      />
    </div>
  );
});

export default CommentCard;
