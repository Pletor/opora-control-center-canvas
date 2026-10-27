import { PLANNED_NOTICE, type AgentContext } from "../logic/agent-context";

const UNKNOWN = "nedostupné";

/** Panel „Pracovní kontext agenta“: kde prvek žije, aby agent i člověk věděli, na co sahají. */
export default function AgentContextPanel({ context }: { context: AgentContext }) {
  const { environment, host, page, componentPath, repo } = context;
  return (
    <section className="element-detail__context" aria-label="Pracovní kontext agenta">
      <h3 className="element-detail__context-title">Pracovní kontext agenta</h3>
      <dl className="element-detail__facts">
        <dt className="element-detail__fact-label">Prostředí</dt>
        <dd className="element-detail__fact">
          {environment ? <span className="element-detail__badge">{environment}</span> : "Sdílená struktura"}
        </dd>
        <dt className="element-detail__fact-label">Doména</dt>
        <dd className="element-detail__fact">{host ?? UNKNOWN}</dd>
        <dt className="element-detail__fact-label">Stránka</dt>
        <dd className="element-detail__fact">{page ? `${page.name} · ${page.id}` : UNKNOWN}</dd>
        {page?.goal ? <><dt className="element-detail__fact-label">Cíl stránky</dt><dd className="element-detail__fact">{page.goal}</dd></> : null}
        {page?.feel ? <><dt className="element-detail__fact-label">Působení</dt><dd className="element-detail__fact">{page.feel}</dd></> : null}
        <dt className="element-detail__fact-label">Komponenta / uzel</dt>
        <dd className="element-detail__fact">{componentPath.length ? componentPath.join(" / ") : "Stránka sama"}</dd>
        <dt className="element-detail__fact-label">{repo?.kind === "planned" ? "Navržená cesta" : "Cesta v repozitáři"}</dt>
        <dd className="element-detail__fact">
          <code className="element-detail__path">{repo ? repo.path : UNKNOWN}</code>
        </dd>
      </dl>
      {repo?.kind === "planned" ? <p className="element-detail__notice">{PLANNED_NOTICE}</p> : null}
    </section>
  );
}
