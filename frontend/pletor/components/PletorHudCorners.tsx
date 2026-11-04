import type { HudState } from "../logic/hud-state";

/** Rohové readouty kolem jádra a štítek stavu pod ním (`label` z hudLabel); jen čtou, co dal rodič. */
export default function PletorHudCorners({ project, brain, state, label, escalations, fps }: { project: string; brain: { name: string; plan: string; local: boolean }; state: HudState; label: string; escalations: number; fps: number }) {
  return (
    <>
      <div className="pletor-hud__corner pletor-hud__corner--tl">PRJ <span>{project || "—"}</span><br />MOZEK <span>{brain.name}</span></div>
      <div className="pletor-hud__corner pletor-hud__corner--tr">FPS <span>{fps || "—"}</span></div>
      <div className="pletor-hud__corner pletor-hud__corner--bl">STAV <span>{label}</span></div>
      <div className="pletor-hud__corner pletor-hud__corner--br">ESK <span>{escalations}</span></div>
      <div className={`pletor-hud__tag pletor-hud__tag--${state}`} role="status">{label}</div>
      <div className={`pletor-hud__brain pletor-hud__brain--${brain.local ? "local" : "cloud"}`}>MOZEK · {brain.name} · {brain.plan}</div>
    </>
  );
}
