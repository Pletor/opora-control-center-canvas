// Ctrl+S (⌘S) v Editoru uloží verzi plátna — i když je fokus v poli. Prohlížečové „Uložit stránku“
// se potlačí vždy, když je zkratka zapnutá. Pravidlo klávesy je čisté `isSaveShortcut`.
import { useEffect, useRef } from "react";
import { isSaveShortcut } from "@/editor/canvas/save-versions/logic/save-versions";

export function useSaveShortcut({ enabled, onSave }: { enabled: boolean; onSave: () => void }) {
  const latest = useRef(onSave);
  latest.current = onSave;
  useEffect(() => {
    if (!enabled) return;
    const listener = (event: KeyboardEvent) => {
      if (!isSaveShortcut(event)) return;
      event.preventDefault();
      event.stopPropagation();
      if (!event.repeat) latest.current();
    };
    window.addEventListener("keydown", listener, true);
    return () => window.removeEventListener("keydown", listener, true);
  }, [enabled]);
}
