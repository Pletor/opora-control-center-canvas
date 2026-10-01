import type { CSSProperties, ReactNode } from "react";
import type { Block } from "@/editor/node-detail/content/logic/block-commands";
import { blockLook, linkChips, type LinkTarget } from "@/editor/node-detail/content/logic/block-view";

/**
 * Jeden řádek osnovy: šipka (jen když má blok děti), kulička, pole textu a odkazy.
 * Dílek nic neukládá a nic nepočítá — dostane hotový blok a každou změnu hlásí rodiči
 * (`BlockOutline`), který drží bloky, kurzor, paletu i sbalení.
 */
export default function BlockRow({
  block,
  index,
  label,
  readOnly,
  targets,
  collapsible,
  collapsed,
  registerField,
  onToggle,
  onChange,
  onKeyDown,
  onPaste,
  onBlur,
  onOpenNode,
  children,
}: {
  block: Block;
  /** Pořadí v celé osnově: drží popisek pole i nápovědu v prvním řádku. */
  index: number;
  label: string;
  readOnly: boolean;
  targets: LinkTarget[];
  collapsible: boolean;
  collapsed: boolean;
  registerField: (field: HTMLTextAreaElement | null) => void;
  onToggle: () => void;
  onChange: (text: string, caret: number) => void;
  onKeyDown: (event: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  onPaste: (event: React.ClipboardEvent<HTMLTextAreaElement>) => void;
  onBlur: () => void;
  onOpenNode?: (nodeId: string) => void;
  /** Paleta příkazů nebo odkazů, když je otevřená právě nad tímto řádkem. */
  children?: ReactNode;
}) {
  const look = blockLook(block.text);
  const chips = linkChips(block.text, targets);
  return (
    <div
      className="block-outline__row"
      data-testid="block-row"
      data-depth={block.depth}
      data-heading={look.heading || undefined}
      data-mark={look.mark ?? undefined}
      data-collapsed={collapsed ? "true" : undefined}
      style={{ "--block-depth": block.depth } as CSSProperties}
    >
      {collapsible ? (
        <button
          type="button"
          className="block-outline__toggle"
          data-testid="block-toggle"
          aria-expanded={!collapsed}
          aria-label={(collapsed ? "Rozbalit blok " : "Sbalit blok ") + (index + 1)}
          onMouseDown={(e) => e.preventDefault()}
          onClick={onToggle}
        >
          {collapsed ? "▶" : "▼"}
        </button>
      ) : (
        <span className="block-outline__gap" aria-hidden="true" />
      )}
      <span className="block-outline__bullet" aria-hidden="true" />
      <textarea
        ref={registerField}
        className="block-outline__input"
        aria-label={label + " · blok " + (index + 1)}
        rows={1}
        readOnly={readOnly}
        value={block.text}
        placeholder={index === 0 ? "Pište. Enter = další blok, Tab = zanořit, / = příkazy" : ""}
        onChange={(e) => !readOnly && onChange(e.target.value.replace(/\n/g, " "), e.target.selectionStart)}
        onKeyDown={onKeyDown}
        onPaste={onPaste}
        onBlur={onBlur}
      />
      {chips.length > 0 && (
        <span className="block-outline__links">
          {chips.map((chip, i) =>
            chip.id ? (
              <button
                key={i}
                type="button"
                className="block-outline__link"
                data-testid="block-link"
                onClick={() => onOpenNode?.(chip.id as string)}
                title={"Otevřít uzel " + chip.name}
              >
                ↗ {chip.name}
              </button>
            ) : (
              <span
                key={i}
                className="block-outline__link block-outline__link--unresolved"
                data-testid="block-link-unresolved"
              >
                ? {chip.name}
              </span>
            ),
          )}
        </span>
      )}
      {children}
    </div>
  );
}
