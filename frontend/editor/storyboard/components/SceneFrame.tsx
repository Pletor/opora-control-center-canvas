// Webová scéna v sandboxovaném iframe: dokument (srcdoc s CSP a runtime) se vykreslí ve velikosti storyboardu a zmenší
// na cílové w×h. Po načtení dostane storyboard (bez html, ten už má), skryté vrstvy a podklady, pak čas; změna t posílá
// jen `seek`. Iframe se přenačte jen při změně dokumentu. Kliky nebere (pointer-events: none), chyby hlásí nahoru.
import { useEffect, useMemo, useRef, useState } from "react";
import type { Storyboard } from "../logic/storyboard-model";
import "../styles/storyboard.css";

type Loaded = { srcdoc: string };

export default function SceneFrame({ html, board, t, hidden, assets, w, h, className, onError, onReady }: {
  /** Hotový srcdoc (`sceneDocument`). */
  html: string;
  board: Storyboard;
  t: number;
  /** Id schovaných vrstev scény. */
  hidden: string[];
  /** Podklady podle `assets[].id` jako data URL. */
  assets: Readonly<Record<string, string>>;
  /** Cílové rozměry v px. */
  w: number;
  h: number;
  className?: string;
  onError?: (message: string) => void;
  onReady?: () => void;
}) {
  const ref = useRef<HTMLIFrameElement>(null);
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const tRef = useRef(t);
  tRef.current = t;
  const callbacks = useRef({ onError, onReady });
  callbacks.current = { onError, onReady };
  const ready = loaded?.srcdoc === html;
  const lite = useMemo(() => (board.scene ? { ...board, scene: { ...board.scene, html: "" } } : board), [board]);
  const hiddenKey = hidden.join(",");
  const { w: sw, h: sh } = board.size;
  const scale = Math.min(w / sw, h / sh);

  const post = (message: unknown) => ref.current?.contentWindow?.postMessage(message, "*");
  useEffect(() => {
    if (!ready) return;
    post({ type: "board", board: lite, hidden: hiddenKey ? hiddenKey.split(",") : [], assets });
    post({ type: "seek", t: tRef.current });
  }, [ready, loaded, lite, hiddenKey, assets]);
  useEffect(() => { if (ready) post({ type: "seek", t }); }, [ready, t]);
  useEffect(() => {
    const listen = (event: MessageEvent) => {
      if (!ref.current || event.source !== ref.current.contentWindow) return;
      const data = event.data as { type?: string; message?: string } | null;
      if (data?.type === "error") callbacks.current.onError?.(String(data.message ?? "neznámá chyba"));
      else if (data?.type === "ready") callbacks.current.onReady?.();
    };
    window.addEventListener("message", listen);
    return () => window.removeEventListener("message", listen);
  }, []);

  return (
    <div className={"scene-frame" + (className ? " " + className : "")} style={{ width: w, height: h }} aria-hidden="true">
      <iframe key={html} ref={ref} className="scene-frame__view" title="Webová scéna" sandbox="allow-scripts" srcDoc={html} tabIndex={-1}
        style={{ width: sw, height: sh, transform: `scale(${scale})` }} onLoad={() => setLoaded({ srcdoc: html })} />
    </div>
  );
}
