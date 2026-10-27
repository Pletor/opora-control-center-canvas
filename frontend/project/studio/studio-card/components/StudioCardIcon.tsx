import { STUDIO_ICONS, type StudioIconName } from "../logic/studio-icons";

/** Ikona druhu karty (Lucide, převzatá z prototypu); jen kresba, čtečka ji přeskočí. */
export default function StudioCardIcon({ name }: { name: StudioIconName }) {
  return <svg className="studio-card__icon-svg" aria-hidden="true" focusable="false" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    {STUDIO_ICONS[name].map(([tag, attrs], index) => {
      if (tag === "path") return <path key={index} {...attrs}/>;
      if (tag === "circle") return <circle key={index} {...attrs}/>;
      if (tag === "rect") return <rect key={index} {...attrs}/>;
      if (tag === "line") return <line key={index} {...attrs}/>;
      return <ellipse key={index} {...attrs}/>;
    })}
  </svg>;
}
