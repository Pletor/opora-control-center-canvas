import { researchContent } from "../logic/research-content";

export default function ResearchContent({ content }: { content: string }) {
  const fields = researchContent(content);
  if (!fields) return <div className="research-inspector__content">{content || "Bez dalšího obsahu."}</div>;
  return <div className="research-inspector__content">
    {fields.map((field, index) => <div className="research-inspector__content-field" key={`${field.label}:${index}`}><strong>{field.label}</strong><p>{field.text}</p></div>)}
    <details className="research-inspector__raw"><summary>Úplná zdrojová data</summary><div>{content}</div></details>
  </div>;
}
