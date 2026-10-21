import { reconciliationLink, type ReconciliationBinding } from "../logic/reconciliation";

export default function BindingIdentity({ binding }: { binding: ReconciliationBinding }) {
  const link = reconciliationLink(binding);
  return <dl className="github-reconciliation__identity">
    <dt>Repozitář</dt><dd>{binding.repository.fullName} · číselné ID <code>{binding.repository.id}</code></dd>
    <dt>Pull request</dt><dd>{link ? <a href={link} target="_blank" rel="noopener noreferrer">PR #{binding.pr.number}</a> : `PR #${binding.pr.number}`} · číselné ID <code>{binding.pr.id}</code></dd>
    <dt>Zdrojový repozitář</dt><dd><code>{binding.pr.headRepoId}</code></dd>
    <dt>Cílová větev</dt><dd><code>{binding.repository.baseBranch}</code></dd>
    <dt>Vázaná přijatá revize plánu</dt><dd><code>{binding.acceptedRevision}</code></dd>
    <dt>SHA hlavy při založení vazby</dt><dd><code>{binding.enrolledHeadSha}</code></dd>
    <dt>Zdroj serverové identity</dt><dd><code>{binding.identityEvidenceId}</code></dd>
  </dl>;
}
