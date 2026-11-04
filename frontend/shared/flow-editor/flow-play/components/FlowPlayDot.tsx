import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { browserMotionEnv, ParticleAnimator } from "../../flow-motion/logic/particle-animator";

type Props = { root: HTMLElement | null; edgeId: string; label: string; stamp: number; duration: number };
type Host = { group: Element; path: SVGPathElement; mid: { x: number; y: number } };

/** Bod s popiskem dat, který proletí po hraně vybrané kroku. Vykreslí se přímo do SVG skupiny hrany React Flow (portál),
 * takže sdílí její souřadnice, zoom i posun plátna; polohu bodu píše sdílený animátor pohybu (jako Studio). Hrana, která
 * na plátně není (sbalený rámec), bod nedostane. */
export default function FlowPlayDot({ root, edgeId, label, stamp, duration }: Props) {
  const animator = useRef<ParticleAnimator | null>(null);
  const dot = useRef<SVGCircleElement>(null);
  const [host, setHost] = useState<Host | null>(null);

  useEffect(() => {
    const motion = new ParticleAnimator(browserMotionEnv());
    motion.attach(); animator.current = motion;
    return () => motion.detach();
  }, []);

  useEffect(() => {
    const group = root?.querySelector(`.react-flow__edge[data-id="${CSS.escape(edgeId)}"]`);
    const path = group?.querySelector<SVGPathElement>("path.react-flow__edge-path");
    setHost(group && path ? { group, path, mid: path.getPointAtLength(path.getTotalLength() / 2) } : null);
  }, [root, edgeId, stamp]);

  useEffect(() => {
    if (!host || !dot.current || !animator.current) return;
    return animator.current.add({ dot: dot.current, path: host.path, mode: "once", delay: 0, duration });
  }, [host, stamp, duration]);

  if (!host) return null;
  return createPortal(<g className="flow-play-dot" data-testid="flow-play-dot" aria-hidden="true">
    <circle ref={dot} className="flow-play-dot__point" r={6} visibility="hidden"/>
    {label && <text className="flow-play-dot__label" x={host.mid.x} y={host.mid.y - 12} textAnchor="middle">{label}</text>}
  </g>, host.group);
}
