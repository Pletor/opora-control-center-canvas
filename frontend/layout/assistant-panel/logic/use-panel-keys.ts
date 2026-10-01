// Klávesové zkratky panelu. Esc zmenší panel jen tehdy, když je fokus v panelu (jinak by zavíral
// dialogy a výběr na plátně). Alt+↑ / Alt+↓ přepínají úkoly globálně, dokud je panel otevřený, ale
// nikdy, když uživatel píše do pole jinde v aplikaci.
import { useEffect, type RefObject } from "react";

function editableOutside(target: EventTarget | null, root: HTMLElement | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (root?.contains(target)) return false;
  return target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName);
}

export function usePanelKeys(
  open: boolean,
  root: RefObject<HTMLElement | null>,
  onShrink: () => void,
  onStep: (step: -1 | 1) => void,
): void {
  useEffect(() => {
    if (!open) return;
    const key = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.isComposing) return;
      if (e.key === "Escape" && !e.altKey && !e.ctrlKey && !e.metaKey) {
        if (root.current && e.target instanceof Node && root.current.contains(e.target)) {
          e.preventDefault();
          onShrink();
        }
        return;
      }
      if (e.altKey && !e.ctrlKey && !e.metaKey && (e.key === "ArrowUp" || e.key === "ArrowDown")) {
        if (editableOutside(e.target, root.current)) return;
        e.preventDefault();
        onStep(e.key === "ArrowUp" ? -1 : 1);
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [open, root, onShrink, onStep]);
}
