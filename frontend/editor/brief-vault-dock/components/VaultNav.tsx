// Vnitřní menu Schránky: hledání, skupiny sekcí s počty (kde je práce) a vlastník schránky dole.
// Jen zobrazení; vybranou sekci a dotaz drží rodič (BriefVaultDock) a změny hlásí callbackem.
import { SECTION_GROUPS, type SectionCounts, type SectionId } from "../logic/vault-dock-model";

export function SectionIcon({ path }: { path: string }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={path} /></svg>
  );
}

export default function VaultNav({ section, counts, query, owner, onSection, onQuery }: {
  section: SectionId;
  counts: SectionCounts;
  query: string;
  owner: string;
  onSection: (id: SectionId) => void;
  onQuery: (query: string) => void;
}) {
  return (
    <nav className="vault-dock__nav" aria-label="Sekce schránky">
      <label className="vault-dock__search">
        <SectionIcon path="M11 4a7 7 0 100 14 7 7 0 000-14zM20 20l-3.5-3.5" />
        <input type="search" aria-label="Hledat ve schránce" placeholder="Hledat ve schránce" value={query}
          onChange={(event) => onQuery(event.target.value)} />
      </label>
      {SECTION_GROUPS.map((group) => (
        <div key={group.label} role="group" aria-label={group.label} className="vault-dock__groupbox">
          <div className="vault-dock__group">{group.label}</div>
          {group.items.map((item) => (
            <button key={item.id} type="button" className="vault-dock__item" aria-current={section === item.id ? "page" : undefined}
              onClick={() => onSection(item.id)}>
              <SectionIcon path={item.icon} />
              <span className="vault-dock__label">{item.label}</span>
              {!!counts[item.id] && <span className="vault-dock__count">{counts[item.id]}</span>}
            </button>
          ))}
        </div>
      ))}
      <div className="vault-dock__owner">Schránka {owner}</div>
    </nav>
  );
}
