import type { ReactNode } from "react";

/** Opened only by explicitly selecting a content block, never by selecting its node. */
export default function BlockEditorDrawer({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  return <aside className="node-library node-library--open" aria-label="Editor bloku" data-testid="node-library-drawer">
    <header className="node-library__head">
      <strong className="node-library__title">{title}</strong>
      <button type="button" className="node-library__close" aria-label="Zavřít editor bloku" onClick={onClose}>✕</button>
    </header>
    <div className="node-library__body">{children}</div>
  </aside>;
}
