// Drobek průchozího řetězu: vrstvy, které obsahují jen jednu dlaždici, se nekreslí a zůstane po nich
// „AmpleLab › Projekty › Trénování“; každý článek vstoupí do své vrstvy na plátně.
import type { ChainLink } from "../logic/tower-view";

export default function TowerChain({ chain, onEnterLayer }: { chain: ChainLink[]; onEnterLayer: (id: string) => void }) {
  if (!chain.length) return null;
  return (
    <nav className="tower-chain" aria-label="Průchozí vrstvy">
      {chain.map((link, index) => (
        <span key={link.id} className="tower-chain__item">
          {index > 0 && <span className="tower-chain__sep" aria-hidden="true">›</span>}
          <button type="button" className="tower-chain__link" title="Vstoupit do vrstvy" onClick={() => onEnterLayer(link.id)}>{link.name}</button>
        </span>
      ))}
    </nav>
  );
}
