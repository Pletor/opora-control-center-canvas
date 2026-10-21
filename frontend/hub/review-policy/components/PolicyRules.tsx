import type { PolicyRules as Rules } from "../logic/review-policy";

export default function PolicyRules({ rules }: { rules: Rules }) {
  return <div className="review-policy__rules">
    <h4>Povinné kontroly</h4><ul>{rules.requiredChecks.map(check => <li key={`${check.appId}:${check.name}`}><code>{check.name}</code> · GitHub app ID <code>{check.appId}</code></li>)}</ul>
    <p>Povolená ID účtů reviewerů: {rules.reviewerIds.join(", ")}</p>
    <p>Minimum schválení kódu: {rules.minimumCodeApprovals} · minimum schválení zadání: {rules.minimumPlanApprovals} · platnost pozorování: {rules.maxObservationAgeSeconds} sekund.</p>
  </div>;
}
