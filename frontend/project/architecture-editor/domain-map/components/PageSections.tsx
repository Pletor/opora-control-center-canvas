import type { PageSection } from "@/shared/types/logic/types";
import { SECTION_ROLE_LABELS } from "../logic/page-site";

/** Sekce stránky jako drobné štítky role + název; `detailed` přidá záměr (přehled ve formuláři). Jen ke čtení: sekce navrhuje agent. */
export default function PageSections({ sections, detailed = false }: { sections?: PageSection[]; detailed?: boolean }) {
  if (!sections?.length) return null;
  return <ul className={"domain-map__sections" + (detailed ? " domain-map__sections--detailed" : "")} aria-label="Sekce stránky">
    {sections.map((section) => <li key={section.id} className="domain-map__section" title={section.intent || undefined} data-testid={"page-section-" + section.id}>
      <span className="domain-map__section-role">{SECTION_ROLE_LABELS[section.role] ?? section.role}</span>
      <span className="domain-map__section-name">{section.name}</span>
      {detailed && section.intent && <span className="domain-map__section-intent">{section.intent}</span>}
    </li>)}
  </ul>;
}
