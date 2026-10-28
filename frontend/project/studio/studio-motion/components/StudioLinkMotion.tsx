import { useEffect, useRef } from "react";
import { useMotionAnimator } from "../logic/motion-context";
import { BASE_CYCLE_MS, cycleMs, DOTS_PER_LINK, PASS_HOP_MS, type LinkMotion } from "../logic/motion-plan";
import "../styles/studio-motion.css";

type Props = {
  /** Trasa vazby (SVG `d`) v souřadnicích plátna. */
  d: string;
  /** Střed trasy pro zastavenou tečku selhání a štítek. */
  mid: { x: number; y: number };
  motion: LinkMotion | undefined;
};

/** Pohyb jedné vazby Studia ve Skutečnosti: tečky po trase, kde se staví (polohu píše animátor plátna přímo do SVG),
 * tečky v barvě ověření po vazbě přechodu cesty, která se právě přehrává, jednorázová tečka nově ověřené cesty, zastavená červená tečka s křížkem v půli trasy u prvního selhání cesty (s
 * důvodem v tooltipu) a štítky „staví se“ / „cesta běží“, které nesou stav, když je pohyb omezený. */
export default function StudioLinkMotion({ d, mid, motion }: Props) {
  const animator = useMotionAnimator();
  const track = useRef<SVGPathElement>(null);
  const dots = useRef<(SVGCircleElement | null)[]>([]);
  const building = motion?.building ?? null;
  const passStamp = motion?.pass?.stamp ?? null;
  const passDelay = motion?.pass?.delay ?? 0;
  const running = !!motion?.running;
  /** Sloty teček: stavba 0…DOTS-1, průchod DOTS, běh cesty DOTS+1…2·DOTS. */
  const runningSlot = (index: number) => DOTS_PER_LINK + 1 + index;

  useEffect(() => {
    const path = track.current;
    if (!animator || !path) return;
    const removers: (() => void)[] = [];
    if (building !== null) for (let index = 0; index < DOTS_PER_LINK; index++) {
      const dot = dots.current[index];
      if (dot) removers.push(animator.add({ dot, path, mode: "loop", cycle: cycleMs(building), index, dots: DOTS_PER_LINK }));
    }
    const once = dots.current[DOTS_PER_LINK];
    if (passStamp && once) removers.push(animator.add({ dot: once, path, mode: "once", delay: passDelay, duration: PASS_HOP_MS }));
    if (running) for (let index = 0; index < DOTS_PER_LINK; index++) {
      const dot = dots.current[runningSlot(index)];
      if (dot) removers.push(animator.add({ dot, path, mode: "loop", cycle: BASE_CYCLE_MS, index, dots: DOTS_PER_LINK }));
    }
    return () => removers.forEach((remove) => remove());
  }, [animator, d, building, passStamp, passDelay, running]);

  if (!motion) return null;
  return <g className="studio-motion" data-testid="studio-motion">
    <path ref={track} className="studio-motion__track" d={d}/>
    {building !== null && Array.from({ length: DOTS_PER_LINK }, (_, index) =>
      <circle key={index} ref={(el) => { dots.current[index] = el; }} className="studio-motion__dot" r={2.5} visibility="hidden" aria-hidden="true"/>)}
    {passStamp && <circle key={passStamp} ref={(el) => { dots.current[DOTS_PER_LINK] = el; }} className="studio-motion__dot studio-motion__dot--pass" r={2.5} visibility="hidden" aria-hidden="true" data-testid="studio-motion-pass"/>}
    {running && Array.from({ length: DOTS_PER_LINK }, (_, index) =>
      <circle key={"running" + index} ref={(el) => { dots.current[runningSlot(index)] = el; }} className="studio-motion__dot studio-motion__dot--running" r={2.5} visibility="hidden" aria-hidden="true" data-testid="studio-motion-running"/>)}
    {building !== null && <text className="studio-motion__label" x={mid.x} y={mid.y - 10} textAnchor="middle">staví se</text>}
    {motion.running && <text className="studio-motion__label studio-motion__label--running" x={mid.x} y={mid.y + 18} textAnchor="middle">
      <title>{motion.running.title}</title>cesta běží
    </text>}
    {motion.failure && <g className="studio-motion__failure" transform={`translate(${mid.x} ${mid.y})`} data-testid="studio-motion-failure" role="img" aria-label={motion.failure.title}>
      <title>{motion.failure.title}</title>
      <circle className="studio-motion__failure-dot" r={6}/>
      <path className="studio-motion__failure-cross" d="M -2.6 -2.6 L 2.6 2.6 M 2.6 -2.6 L -2.6 2.6"/>
    </g>}
  </g>;
}
