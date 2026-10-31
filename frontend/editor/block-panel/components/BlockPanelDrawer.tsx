// Obal bočního menu (panel karty): stejná zásuvka od levé hrany plátna jako dřív Knihovna, jen širší (360 px),
// aby se stopa práce dala číst. Vlastní hlavičku nemá: druh, název a zavírací × nese hlavička panelu podle návrhu.
// Otevře se výběrem bloku, nebo výslovně z karty (klik na postup na tváři karty); samotný výběr karty ji neotevírá.
import type { ReactNode } from "react";

export default function BlockPanelDrawer({ children }: { children: ReactNode }) {
  return <aside className="node-library node-library--open node-library--wide" aria-label="Boční menu karty" data-testid="node-library-drawer">
    <div className="node-library__body">{children}</div>
  </aside>;
}
