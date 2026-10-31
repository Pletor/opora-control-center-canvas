// Obal bočního menu bloku: stejná zásuvka od levé hrany plátna jako dřív Knihovna, jen širší (360 px),
// aby se stopa práce dala číst. Otevře se jen výběrem konkrétního bloku, nikdy výběrem samotné karty.
import type { ReactNode } from "react";

export default function BlockPanelDrawer({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  return <aside className="node-library node-library--open node-library--wide" aria-label="Boční menu bloku" data-testid="node-library-drawer">
    <header className="node-library__head">
      <strong className="node-library__title">{title}</strong>
      <button type="button" className="node-library__close" aria-label="Zavřít boční menu bloku" onClick={onClose}>✕</button>
    </header>
    <div className="node-library__body">{children}</div>
  </aside>;
}
