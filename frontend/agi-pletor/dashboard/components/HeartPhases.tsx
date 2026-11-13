import type { BatchView } from "../logic/heart-explain";

const COLORS = ["accent", "ink", "dim", "error", "line"];

/** „Kam šel čas dávek“: každá dávka má větu, proužek podílů fází, nejpomalejší volání a selhání. */
export default function HeartPhases({ batches }: { batches: BatchView[] }) {
  if (batches.length === 0) return <p className="pletor-dashboard__empty">Zatím žádné dávky.</p>;
  return (
    <ul className="heart-explain__batches">
      {batches.map((b, i) => (
        <li key={`${b.at}-${i}`} className="heart-explain__batch">
          <p className="heart-explain__headline">{b.headline}{b.truncated && " (zkráceno)"}</p>
          <div className="heart-explain__bar" role="img" aria-label="Podíl fází">
            {b.phases.map((p, k) => (
              <span key={p.id} className={`heart-explain__phase heart-explain__phase--${COLORS[k % COLORS.length]}`} style={{ width: `${p.percent}%` }} title={`${p.label} ${p.seconds}`} />
            ))}
          </div>
          <p className="heart-explain__legend">{b.phases.map((p) => `${p.label} ${p.seconds}`).join(" · ")}</p>
          {b.slowest.length > 0 && <p className="heart-explain__slow">Nejpomalejší: {b.slowest.join("; ")}</p>}
          {b.failures.length > 0 && <p className="heart-explain__fail">Selhání: {b.failures.join("; ")}</p>}
        </li>
      ))}
    </ul>
  );
}
