// Pruh pokrytí schránky s legendou: každý list zadání v právě jednom segmentu (MVP vloženo · vloženo ·
// v researchu · uloženo · změněno). Sdílí ho záložka Schránka, vstup „Otevřít schránku“ i Přehled v okně.
import { COVERAGE_SEGMENTS, coverageSegments, type Coverage } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import "@/editor/node-detail/brief-vault/styles/brief-vault.css";

export function chaptersLabel(n: number) {
  return n === 1 ? "kapitola" : n >= 2 && n <= 4 ? "kapitoly" : "kapitol";
}

export default function CoverageBar({ coverage, large = false, legend = true, changedMvp = 0 }: {
  coverage: Coverage;
  large?: boolean;
  legend?: boolean;
  /** Kolik změněných kapitol je v MVP: varování MVP neschová. */
  changedMvp?: number;
}) {
  const segments = coverageSegments(coverage);
  return (
    <div className="brief-vault__coverage">
      <div className={"brief-vault__bar" + (large ? " brief-vault__bar--large" : "")} role="img"
        aria-label={`Pokrytí: ${coverage.leaves} ${chaptersLabel(coverage.leaves)}, ` + COVERAGE_SEGMENTS.map((s) => `${s.label} ${coverage[s.key]}`).join(", ")}>
        {segments.map((segment) => (
          <span key={segment.key} className={"brief-vault__segment brief-vault__segment--" + segment.key}
            style={{ width: segment.percent + "%" }} title={`${segment.label}: ${segment.count}`} />
        ))}
      </div>
      {legend && (
        <p className="brief-vault__legend">
          <strong>{coverage.leaves} {chaptersLabel(coverage.leaves)}:</strong>{" "}
          {COVERAGE_SEGMENTS.map((segment, index) => (
            <span key={segment.key} className={"brief-vault__legend-item" + (coverage[segment.key] ? "" : " brief-vault__legend-item--zero")}>
              {index > 0 && " · "}
              <i className={"brief-vault__swatch brief-vault__segment--" + segment.key} aria-hidden="true" />
              {segment.label} {coverage[segment.key]}{segment.key === "changed" && changedMvp > 0 ? ` (z toho MVP ${changedMvp})` : ""}
            </span>
          ))}
        </p>
      )}
    </div>
  );
}
