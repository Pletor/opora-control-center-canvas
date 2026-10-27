import { useEffect, useMemo, useRef } from "react";
import { useFlowAnimatorContext } from "../logic/flow-context";
import { linkParticles } from "../logic/model-particles";
import type { LinkFlow } from "../logic/run-view";

/** Částice jedné vazby MODELu podle vypočteného toku: tečky v barvě typu portu (přijato) a růžové (odmítnuto, chybová
 * odpověď). Polohu píše animátor plátna přímo do SVG; tady se jen vykreslí kruhy a přihlásí. Vykresluje se uvnitř
 * vrstvy vazeb, takže souřadnice jsou souřadnice plátna. */
export default function ModelLinkFlow({ linkId, d, flow }: { linkId: string; d: string; flow: LinkFlow }) {
  const animator = useFlowAnimatorContext();
  const track = useRef<SVGPathElement>(null);
  const dots = useRef<(SVGCircleElement | null)[]>([]);
  const particles = useMemo(() => linkParticles(flow), [flow]);

  useEffect(() => {
    const path = track.current;
    if (!animator || !path) return;
    const removers = particles.flatMap((particle, index) => { const dot = dots.current[index]; return dot ? [animator.add(dot, path, particle)] : []; });
    return () => removers.forEach((remove) => remove());
  }, [animator, d, particles]);

  if (!particles.length) return null;
  return <g className="studio-model-run__flow" data-testid={"studio-model-flow-" + linkId} data-particles={particles.length}>
    <path ref={track} className="studio-model-run__track" d={d}/>
    {particles.map((particle, index) => <circle key={`${particle.kind}-${particle.ordinal}`} ref={(el) => { dots.current[index] = el; }}
      className={"studio-model-run__particle studio-model-run__particle--" + particle.kind} r={particle.kind === "accepted" ? 3.1 : 3.3}
      style={{ ["--studio-particle" as string]: particle.color }} aria-hidden="true" data-kind={particle.kind}>
      <title>{`MODEL · ${particle.kind}: ${particle.amount} jednotek/tick`}</title>
    </circle>)}
  </g>;
}
