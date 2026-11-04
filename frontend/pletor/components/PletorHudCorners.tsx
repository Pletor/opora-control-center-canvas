import { HUD_LABEL, type HudState } from "../logic/hud-palette";

/** Rohové readouty kolem jádra a štítek stavu pod ním; jen čtou, co dal rodič. */
export default function PletorHudCorners({ project, brain, state, escalations, fps }: { project: string; brain: string; state: HudState; escalations: number; fps: number }) {
  return (
    <>
      <div className="pletor-hud__corner pletor-hud__corner--tl">PRJ <span>{project || "—"}</span><br />MOZEK <span>{brain}</span></div>
      <div className="pletor-hud__corner pletor-hud__corner--tr">FPS <span>{fps || "—"}</span></div>
      <div className="pletor-hud__corner pletor-hud__corner--bl">STAV <span>{HUD_LABEL[state]}</span></div>
      <div className="pletor-hud__corner pletor-hud__corner--br">ESK <span>{escalations}</span></div>
      <div className={`pletor-hud__tag pletor-hud__tag--${state}`}>{HUD_LABEL[state]}</div>
    </>
  );
}
