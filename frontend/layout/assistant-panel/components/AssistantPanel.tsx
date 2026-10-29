import { useCallback, useEffect, useRef, useState } from "react";
import HeartChannel from "@/layout/heart-channel/components/HeartChannel";
import { readPrefs, reopenSize, smallerSize, writePrefs, type PanelSize } from "../logic/assistant-prefs";
import { useGate } from "../logic/use-gate";
import { usePanelKeys } from "../logic/use-panel-keys";
import MinimizedBar from "./MinimizedBar";
import PanelHead from "./PanelHead";
import PanelNotice from "./PanelNotice";

/** Kde panel právě je: projekt a pracovní prostor z App. */
export type PanelScope = { projectId: string; workspace: string };

/**
 * Rodič panelu Asistent: kanál člověka do srdce (docs/brain-heart-channel.md). Drží velikost
 * (uloženou jednou pro aplikaci), stav brány projektu a zkratku Esc; obsah je `HeartChannel`, který
 * dostane jen projekt, prostor a stav brány. Zavřený panel nic nevykreslí.
 */
export default function AssistantPanel({ open, scope, onClose }: { open: boolean; scope: PanelScope; onClose: () => void }) {
  const [size, setSizeState] = useState<PanelSize>(() => readPrefs().size);
  const lastExpanded = useRef<PanelSize>(size === "full" ? "full" : "side");
  const root = useRef<HTMLElement>(null);
  const gate = useGate(open, scope.projectId);

  const setSize = useCallback((next: PanelSize) => {
    setSizeState(next);
    writePrefs({ size: next });
    if (next !== "minimized") lastExpanded.current = next;
  }, []);

  // Otevření tlačítkem: poslední velikost, z lišty rovnou panel vpravo.
  const wasOpen = useRef(false);
  useEffect(() => {
    if (open && !wasOpen.current) setSizeState((current) => reopenSize(current));
    wasOpen.current = open;
  }, [open]);

  const shrink = useCallback(() => setSize(smallerSize(size)), [setSize, size]);
  usePanelKeys(open, root, shrink);

  if (!open) return null;
  if (size === "minimized") {
    return <MinimizedBar barRef={root} onExpand={() => setSize(lastExpanded.current)} onClose={onClose} />;
  }

  const content = scope.projectId
    ? <HeartChannel active={open} projectId={scope.projectId} workspace={scope.workspace} gateOn={gate.gateOn} gateFailure={gate.gateFailure} onEnableGate={gate.turnGateOn} />
    : <PanelNotice />;

  return (
    <aside ref={root} className={`assistant-panel assistant-panel--${size}`} aria-label="Asistent">
      <PanelHead size={size} onSize={setSize} onClose={onClose} />
      <div className="assistant-panel__body">{content}</div>
    </aside>
  );
}
