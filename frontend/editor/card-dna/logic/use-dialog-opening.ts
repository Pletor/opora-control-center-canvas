import { useEffect, useRef, type RefObject } from "react";
import { shouldActivateDialog } from "./card-click";

/** Bez časovače: průhledný náhled zachová původní cíl dvojkliku a teprve další
 * pohyb mimo kartu/klávesnice převede tentýž dialog do modálního režimu.
 */
export function useDialogOpening(dialog: RefObject<HTMLDialogElement | null>, origin: HTMLElement | null, close: () => void) {
  const closeRef = useRef(close); closeRef.current = close;
  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    const previousFocus = document.activeElement as HTMLElement | null;
    let preview = !!origin;
    const activate = () => {
      if (!preview) return;
      preview = false; element.close(); element.inert = false;
      element.classList.remove("card-dna--preview"); element.showModal();
    };
    const move = (event: PointerEvent) => {
      if (preview && origin && shouldActivateDialog(origin.getBoundingClientRect(), { x: event.clientX, y: event.clientY })) activate();
    };
    const down = (event: PointerEvent) => {
      if (!preview || !origin || !shouldActivateDialog(origin.getBoundingClientRect(), { x: event.clientX, y: event.clientY })) return;
      event.preventDefault(); event.stopPropagation(); activate();
    };
    const key = (event: KeyboardEvent) => {
      if (!preview || event.isComposing) return;
      if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); closeRef.current(); }
      else if (!["Shift", "Control", "Alt", "Meta"].includes(event.key)) activate();
    };
    if (preview) {
      element.inert = true; element.classList.add("card-dna--preview"); element.show();
      previousFocus?.focus({ preventScroll: true });
    } else element.showModal();
    document.addEventListener("pointermove", move, true);
    document.addEventListener("pointerdown", down, true);
    document.addEventListener("keydown", key, true);
    return () => {
      document.removeEventListener("pointermove", move, true);
      document.removeEventListener("pointerdown", down, true);
      document.removeEventListener("keydown", key, true);
      element.close();
      if (previousFocus?.isConnected) previousFocus.focus({ preventScroll: true });
    };
  }, [dialog, origin]);
}
