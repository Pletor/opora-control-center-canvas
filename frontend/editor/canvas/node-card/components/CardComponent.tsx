// Komponenta na kartě (docs/architektura-pro-agenty.md §3.3): technologie jako jeden tichý řádek a stavy
// jako drobné čipy pod ním. Obojí píše agent; karta to jen ukazuje a nic tu nejde upravit. Bez zapsaných
// hodnot se dílek nevykreslí vůbec, takže karta bez komponenty vypadá jako dřív.
export default function CardComponent({ tech, states }: { tech: string | null; states: string[] }) {
  if (!tech && !states.length) return null;
  return (
    <div className="node-card__component" aria-label="Komponenta">
      {tech && <p className="node-card__tech" title="Technologie realizace (zapsal agent)">{tech}</p>}
      {states.length > 0 && (
        <ul className="node-card__states" aria-label="Stavy komponenty">
          {states.map((state) => <li key={state} className="node-card__state">{state}</li>)}
        </ul>
      )}
    </div>
  );
}
