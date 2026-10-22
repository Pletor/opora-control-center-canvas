import { useEffect, useLayoutEffect, useRef, useState, type PointerEvent } from "react";
import type { GraphDoc } from "@coldtea/pr-lens-schema";
import { boxStyle, fitCamera, panBy, unionBox, zoomAt, type Box, type Camera } from "../logic/overlay";
import type { Drawn } from "../logic/stage-render";
import type { Lens } from "../logic/walkthrough";

export type Selection = { kind: "node"; id: string } | { kind: "message"; flow: string; id: string } | null;
type Props = { drawn: Drawn; title: string; lens: Lens; flow: string | null; focus: Box[]; selected: Selection; doc: GraphDoc; onSelect: (selection: Selection) => void };

/**
 * Obrázek rendereru jako `<img>` z Blob URL: skripty v SVG neběží, SMIL animace ano a do DOM se
 * nevkládá žádný text specu jako HTML. Interaktivita je React překryv nad ním: absolutně umístěná
 * tlačítka z rámečků atlasu, přepočtená z jednotek viewBoxu na pixely obrázku v aktuálním přiblížení.
 */
export default function LensViewport({ drawn, title, lens, flow, focus, selected, doc, onSelect }: Props) {
  const viewport = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [camera, setCamera] = useState<Camera>({ scale: 1, x: 0, y: 0 });
  const [src, setSrc] = useState("");
  const drag = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => {
    const url = URL.createObjectURL(new Blob([drawn.svg], { type: "image/svg+xml" }));
    setSrc(url);
    return () => URL.revokeObjectURL(url);
  }, [drawn.svg]);
  useLayoutEffect(() => {
    const element = viewport.current;
    if (!element) return;
    const measure = () => setSize({ width: element.clientWidth, height: element.clientHeight });
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  // Celé plátno, nebo (v průvodci) jen to, na co krok míří: kamera se posadí na obal rámečků.
  const whole = { x: 0, y: 0, width: drawn.width, height: drawn.height };
  const target = unionBox(focus) ?? whole;
  const fitKey = `${drawn.svg.length}:${target.x}:${target.y}:${target.width}:${target.height}:${size.width}:${size.height}`;
  useEffect(() => { if (size.width) setCamera(fitCamera(target, size, 32, focus.length ? 1.2 : 1)); }, [fitKey]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const element = viewport.current;
    if (!element) return;
    const wheel = (event: WheelEvent) => {
      event.preventDefault();
      const rect = element.getBoundingClientRect();
      setCamera(current => zoomAt(current, event.deltaY < 0 ? 1.15 : 1 / 1.15, { x: event.clientX - rect.left, y: event.clientY - rect.top }));
    };
    element.addEventListener("wheel", wheel, { passive: false });
    return () => element.removeEventListener("wheel", wheel);
  }, []);

  function down(event: PointerEvent<HTMLDivElement>) {
    if ((event.target as HTMLElement).closest("button")) return;
    drag.current = { x: event.clientX, y: event.clientY };
    event.currentTarget.setPointerCapture(event.pointerId);
  }
  function move(event: PointerEvent<HTMLDivElement>) {
    if (!drag.current) return;
    const dx = event.clientX - drag.current.x, dy = event.clientY - drag.current.y;
    drag.current = { x: event.clientX, y: event.clientY };
    setCamera(current => panBy(current, dx, dy));
  }
  const zoom = (factor: number) => setCamera(current => zoomAt(current, factor, { x: size.width / 2, y: size.height / 2 }));
  const s = camera.scale;
  const nodeLabel = (id: string) => doc.nodes.find(node => node.id === id)?.label ?? id;
  const messages = Object.entries(drawn.atlas.messages).filter(([key]) => !flow || key === flow)
    .flatMap(([key, items]) => Object.entries(items).map(([id, box]) => ({ flow: key, id, box })));
  const messageLabel = (flowId: string, id: string) => doc.flows.find(item => item.id === flowId)?.messages.find(item => item.id === id)?.label ?? id;
  return <div className="review-lens__viewport" ref={viewport} data-oh-lens-scale={s.toFixed(2)} onPointerDown={down} onPointerMove={move}
    onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }}>
    <div className="review-lens__layer" style={{ transform: `translate(${camera.x}px, ${camera.y}px)` }}>
      {src && <img className="review-lens__image" src={src} alt={title} width={drawn.width * s} height={drawn.height * s} draggable={false} />}
      {Object.entries(drawn.atlas.nodes).map(([id, box]) => <button key={`n:${id}`} type="button" style={boxStyle(box, s)} data-oh-lens-node={id}
        className={`review-lens__hit${selected?.kind === "node" && selected.id === id ? " review-lens__hit--selected" : ""}`}
        aria-label={`Část ${nodeLabel(id)}`} title={nodeLabel(id)} onClick={() => onSelect({ kind: "node", id })} />)}
      {lens === "data-flow" && messages.map(item => <button key={`m:${item.flow}:${item.id}`} type="button" style={boxStyle(item.box, s, 3)}
        data-oh-lens-message={item.id} data-oh-lens-flow={item.flow} title={messageLabel(item.flow, item.id)}
        className={`review-lens__hit review-lens__hit--message${selected?.kind === "message" && selected.id === item.id && selected.flow === item.flow ? " review-lens__hit--selected" : ""}`}
        aria-label={`Krok toku ${messageLabel(item.flow, item.id)}`} onClick={() => onSelect({ kind: "message", flow: item.flow, id: item.id })} />)}
      {focus.map((box, index) => <span key={`f:${index}`} className="review-lens__rim" style={boxStyle(box, s, 6)} data-oh-lens-focus="" aria-hidden="true" />)}
    </div>
    <div className="review-lens__zoom" role="group" aria-label="Přiblížení">
      <button type="button" className="review-lens__zoom-button" aria-label="Oddálit" onClick={() => zoom(1 / 1.25)}>−</button>
      <span className="review-lens__zoom-value">{Math.round(s * 100)} %</span>
      <button type="button" className="review-lens__zoom-button" aria-label="Přiblížit" onClick={() => zoom(1.25)}>+</button>
      <button type="button" className="review-lens__zoom-button" aria-label="Celé plátno" onClick={() => setCamera(fitCamera(whole, size, 24, 1))}>⤢</button>
    </div>
  </div>;
}
