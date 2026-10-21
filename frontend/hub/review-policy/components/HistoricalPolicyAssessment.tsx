import { policyLabels, type PolicyEvaluation } from "../logic/review-policy";

export default function HistoricalPolicyAssessment({ evaluation, schemaVersion }: { evaluation?: PolicyEvaluation; schemaVersion?: number }) {
  return <section aria-label="Historické vyhodnocení pravidel"><h4>Pravidla u tohoto uloženého pozorování</h4>
    {schemaVersion !== 2 && <p>Starší pozorování nemá průkazný interval a pořadí pokusu pro tato pravidla. Je nutné načíst nové pozorování z GitHubu.</p>}
    {evaluation ? <><p>Vyhodnocení při načtení detailu: {policyLabels[evaluation.status]}.</p>
      <p>Revize pravidel <code>{evaluation.policyRevision ?? "nenastavena"}</code> · vyhodnoceno {new Date(evaluation.freshness.evaluatedAt).toLocaleString("cs-CZ")}.</p>
      {!!evaluation.blockers.length && <ul>{evaluation.blockers.map((reason, index) => <li key={index}><code>{reason}</code></li>)}</ul>}</>
      : <p>Vyhodnocení místních pravidel není v tomto detailu dostupné.</p>}
    <p>Tento historický detail není ukazatelem aktuálního splnění. Aktuální stav, pravidla a dobu platnosti uvádí samostatný panel níže.</p>
  </section>;
}
