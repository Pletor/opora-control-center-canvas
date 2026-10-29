// Klávesové zkratky panelu. Esc zmenší panel jen tehdy, když je fokus v panelu (jinak by zavíral
// dialogy a výběr na plátně).
import { useEffect, type RefObject } from "react";

export function usePanelKeys(open: boolean, root: RefObject<HTMLElement | null>, onShrink: () => void): void {
  useEffect(() => {
    if (!open) return;
    const key = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.isComposing) return;
      if (e.key !== "Escape" || e.altKey || e.ctrlKey || e.metaKey) return;
      if (root.current && e.target instanceof Node && root.current.contains(e.target)) {
        e.preventDefault();
        onShrink();
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [open, root, onShrink]);
}
