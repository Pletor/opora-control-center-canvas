import type { HudState } from "../logic/hud-state";

/** Jádro Pletora v okně: jen kreslí stav, který odvodil rodič (hudState, stejný jako HUD). Stav pro čtečky nese štítek pod ním. */
export default function PletorOrb({ state }: { state: HudState }) {
  return (
    <div className={`pletor-orb pletor-orb--${state}`} aria-hidden="true">
      <span className="pletor-orb__ring" />
      <span className="pletor-orb__ring pletor-orb__ring--inner" />
      <span className="pletor-orb__core" />
    </div>
  );
}
