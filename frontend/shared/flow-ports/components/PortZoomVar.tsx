// Neviditelný pomocník uvnitř `<ReactFlow>`: zapisuje `--rf-inv-zoom` (převrácený zoom) a značku
// `data-port-connecting` (právě se táhne vazba) přímo na kořen plátna. Odebírá store React Flow bez
// Reactu, takže se při tahu kolečkem nepřekreslí žádná karta ani tento dílek.
import { useEffect } from "react";
import { useStoreApi } from "@xyflow/react";
import { inverseZoom } from "@/shared/flow-ports/logic/port-labels";

export default function PortZoomVar() {
  const store = useStoreApi();
  useEffect(() => {
    let dom: HTMLElement | null = null;
    let inv = 0;
    let connecting: boolean | null = null;
    const apply = () => {
      const state = store.getState();
      const root = state.domNode;
      if (!root) return;
      const next = inverseZoom(state.transform[2]);
      const active = state.connection.inProgress;
      if (root !== dom || next !== inv) root.style.setProperty("--rf-inv-zoom", String(next));
      if (root !== dom || active !== connecting) {
        if (active) root.setAttribute("data-port-connecting", "");
        else root.removeAttribute("data-port-connecting");
      }
      dom = root; inv = next; connecting = active;
    };
    apply();
    return store.subscribe(apply);
  }, [store]);
  return null;
}
