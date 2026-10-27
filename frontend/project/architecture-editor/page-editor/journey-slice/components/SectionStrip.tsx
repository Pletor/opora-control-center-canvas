import type { SectionChip } from "../logic/page-slice";

/** Pruh sekcí stránky: role · název · čím posouvá a kolik komponent sekci realizuje (sekce bez komponenty varovně).
 * Klik na štítek hlásí `onSelect`: rodič vybere stránku v Detailu prvku, kde se sekce rozebírají (záložka Stránka). */
export default function SectionStrip({ sections, onSelect }: { sections: SectionChip[]; onSelect: () => void }) {
  if (!sections.length) return null;
  return <ul className="journey-slice__sections" aria-label="Sekce stránky" data-testid="architecture-section-strip">
    {sections.map((section) => <li key={section.id}>
      <button type="button" className={"journey-slice__section" + (section.components ? "" : " journey-slice__section--empty")}
        data-testid={"architecture-section-chip-" + section.id} title={section.moves ? "Čím posouvá: " + section.moves : "Rozebrat v Detailu prvku"}
        aria-label={`Sekce ${section.role} ${section.name}, komponent: ${section.components}. Rozebrat v Detailu prvku.`} onClick={onSelect}>
        <span className="journey-slice__section-role">{section.role}</span>
        <span className="journey-slice__section-name">{section.name}</span>
        {section.moves && <span className="journey-slice__section-moves">{section.moves}</span>}
        <span className="journey-slice__section-count">{section.components ? section.components : "⚠ 0"}</span>
      </button>
    </li>)}
  </ul>;
}
