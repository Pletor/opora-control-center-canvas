import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

export default function OverviewDrawer({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  const panel = useRef<HTMLDivElement>(null);
  const latestClose = useRef(onClose);
  latestClose.current = onClose;
  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const element = panel.current;
    const dialog = element?.querySelector<HTMLElement>('[role="dialog"]');
    if (!element || !dialog) return;
    const siblings = [...element.parentElement!.children].filter(child => child !== element);
    const wasInert = siblings.map(child => (child as HTMLElement).inert);
    siblings.forEach(child => { (child as HTMLElement).inert = true; });
    const controls = () => [...dialog.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), summary, [tabindex="0"]')]
      .filter(item => item.getClientRects().length && !item.closest('[inert]'));
    const containFocus = () => {
      if (!dialog.contains(document.activeElement)) (controls()[0] ?? dialog).focus();
    };
    const keyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault(); event.stopPropagation(); latestClose.current(); return;
      }
      if (event.key !== "Tab") return;
      const items = controls(), first = items[0], last = items.at(-1);
      if (!dialog.contains(document.activeElement) || !items.length) {
        event.preventDefault(); (event.shiftKey ? last ?? dialog : first ?? dialog).focus();
      } else if (event.shiftKey && document.activeElement === first) {
        event.preventDefault(); last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault(); first?.focus();
      }
    };
    document.addEventListener("keydown", keyDown, true);
    document.addEventListener("focusin", containFocus, true);
    // A completed mutation can remove its focused confirmation button without a focus event.
    const observer = new MutationObserver(containFocus);
    observer.observe(dialog, { childList: true, subtree: true });
    containFocus();
    return () => {
      observer.disconnect();
      document.removeEventListener("keydown", keyDown, true);
      document.removeEventListener("focusin", containFocus, true);
      siblings.forEach((child, index) => { (child as HTMLElement).inert = wasInert[index]; });
      if (previous?.isConnected) previous.focus();
    };
  }, []);
  return createPortal(<div className="oporahub-overview__overlay" ref={panel} onMouseDown={event => { if (event.target === event.currentTarget) latestClose.current(); }}>
    <section className="oporahub-overview__drawer" role="dialog" aria-modal="true" aria-labelledby="hub-detail-title" tabIndex={-1}>
      <header className="oporahub-overview__drawer-head"><h2 id="hub-detail-title">{title}</h2><button type="button" aria-label="Zavřít detail" onClick={onClose}>✕</button></header>
      <div className="oporahub-overview__drawer-body">{children}</div>
    </section>
  </div>, document.body);
}
