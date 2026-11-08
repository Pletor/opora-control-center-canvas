import "../styles/pletor-dashboard-linie-trial.css";

/**
 * Jak vyzkoušet (docs/navrhy/2026-11-08-linie-zkouska.md, Doplněk): očíslované kroky, které agent poslal s reportem
 * (`tryout.steps`). Bez kroků se nekreslí nic. Detail (Souhrn) i řádek „Čeká na tebe“ kreslí totéž.
 */
export default function LinieTrialSteps({ steps }: { steps: string[] }) {
  if (!steps.length) return null;
  return (
    <div className="linie-trial__how">
      <p className="linie-trial__how-title">Jak vyzkoušet</p>
      <ol className="linie-trial__steps">{steps.map((step, i) => <li key={i}>{step}</li>)}</ol>
    </div>
  );
}
