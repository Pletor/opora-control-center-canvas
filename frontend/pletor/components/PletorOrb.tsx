import type { PletorOrbMode } from "../logic/pletor-orb-mode";

/** Jádro Pletora nad rozhovorem: jen kreslí stav, který odvodil rodič. Stav pro čtečky nese řádek srdce a log zpráv. */
export default function PletorOrb({ mode }: { mode: PletorOrbMode }) {
  return (
    <div className={`pletor-orb pletor-orb--${mode}`} aria-hidden="true">
      <span className="pletor-orb__ring" />
      <span className="pletor-orb__ring pletor-orb__ring--inner" />
      <span className="pletor-orb__core" />
    </div>
  );
}
