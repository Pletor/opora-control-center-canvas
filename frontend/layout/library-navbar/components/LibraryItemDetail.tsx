// Dílek náhled prvku: co dostane model, když prvek pustí na plátno — souvislosti (`@id` přeložené na
// název a účel), kritéria hotovo, invarianty jako musí / nesmí, kroky a šablona. Účel už stojí v řádku
// nad náhledem, proto se neopakuje. Prázdné části se nekreslí. Jen čte prvek z props.
import { relatesLines, type CatalogItem } from "@/editor/component-library/library-catalog/logic/library-catalog";

export default function LibraryItemDetail({ item }: { item: CatalogItem }) {
  const relates = relatesLines(item.relates);
  return (
    <div className="library-navbar__detail" data-testid={"library-detail-" + item.id}>
      {relates.length > 0 && (
        <section className="library-navbar__detail-part">
          <h4 className="library-navbar__detail-title">Souvisí s</h4>
          <ul className="library-navbar__detail-list">
            {relates.map((line) => <li key={line}>{line}</li>)}
          </ul>
        </section>
      )}
      <section className="library-navbar__detail-part">
        <h4 className="library-navbar__detail-title">Hotovo, když</h4>
        <ul className="library-navbar__detail-list">
          {item.done.map((line) => <li key={line}>{line}</li>)}
        </ul>
      </section>
      {item.invariants.length > 0 && (
        <section className="library-navbar__detail-part">
          <h4 className="library-navbar__detail-title">Hranice</h4>
          <ul className="library-navbar__detail-list">
            {item.invariants.map((rule) => (
              <li key={rule.text} className={"library-navbar__detail-rule library-navbar__detail-rule--" + rule.kind}>
                <b className="library-navbar__detail-kind">{rule.kind === "must" ? "musí" : "nesmí"}</b> {rule.text}
              </li>
            ))}
          </ul>
        </section>
      )}
      {item.steps && item.steps.length > 0 && (
        <section className="library-navbar__detail-part">
          <h4 className="library-navbar__detail-title">Kroky</h4>
          <ol className="library-navbar__detail-list">
            {item.steps.map((step) => <li key={step.title}><b>{step.title}</b> — {step.text}</li>)}
          </ol>
        </section>
      )}
      {item.template?.trim() && (
        <section className="library-navbar__detail-part">
          <h4 className="library-navbar__detail-title">Šablona</h4>
          <pre className="library-navbar__detail-code">{item.template}</pre>
        </section>
      )}
    </div>
  );
}
