import { useEffect, useState, type CSSProperties } from "react";
import { animationCss, sanitizeWireframeMetadata } from "./wireframe-model";

type PreviewElement = {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  text?: string;
  name?: string | null;
  strokeColor: string;
  backgroundColor: string;
  customData?: unknown;
};

export default function WireframePreview({ elements }: { elements: readonly PreviewElement[] }) {
  const [scroll, setScroll] = useState(0);
  useEffect(() => {
    const update = () => setScroll(Math.min(240, window.scrollY));
    window.addEventListener("scroll", update, { passive: true });
    update();
    return () => window.removeEventListener("scroll", update);
  }, []);
  const visible = elements
    .map((element) => ({ element, metadata: sanitizeWireframeMetadata(element.customData) }))
    .filter((item): item is { element: PreviewElement; metadata: NonNullable<ReturnType<typeof sanitizeWireframeMetadata>> } => !!item.metadata);
  if (!visible.length) return null;
  const minX = Math.min(...visible.map(({ element }) => element.x));
  const minY = Math.min(...visible.map(({ element }) => element.y));
  const maxX = Math.max(...visible.map(({ element }) => element.x + element.width));
  const maxY = Math.max(...visible.map(({ element }) => element.y + element.height));
  const width = Math.max(1, maxX - minX);
  const height = Math.max(1, maxY - minY);
  return (
    <section className="wireframe-preview" aria-label="Bezpečný náhled wireframu">
      <h3>Náhled</h3>
      <p className="muted">Pouze rozložení a podporované presety; akce se nespouštějí.</p>
      <div className="wireframe-preview-stage" style={{ aspectRatio: `${width} / ${height}` }}>
        {visible.map(({ element, metadata }) => {
          const style = {
            left: `${((element.x - minX) / width) * 100}%`,
            top: `${((element.y - minY) / height) * 100}%`,
            width: `${(element.width / width) * 100}%`,
            height: `${(element.height / height) * 100}%`,
            borderColor: element.strokeColor,
            backgroundColor: element.backgroundColor,
            transform: `translateY(${scroll * (metadata.oporaWireframe.parallax.enabled ? metadata.oporaWireframe.parallax.speed : 0) * -0.08}px)`,
            ...animationCss(metadata.oporaWireframe),
          } as CSSProperties;
          return (
            <div key={element.id} className={`wireframe-preview-item role-${metadata.oporaWireframe.role}`} style={style}>
              {element.name || element.text || metadata.oporaWireframe.component}
            </div>
          );
        })}
      </div>
    </section>
  );
}
