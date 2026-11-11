import type { ElementContext } from "../logic/element-context";
import "../styles/element-context.css";

/** Hlavička plátna logiky prvku místo „knihovna“: druh a název prvku, stránka › box a návrat na plán stránky.
 * Návrat jen hlásí nahoru; adresu a přepnutí pohledu řeší rodič. */
export default function ElementContextHead({ context, onBack }: { context: ElementContext; onBack: () => void }) {
  return <div className="element-context" data-testid="library-element-context">
    <button type="button" className="element-context__back" data-testid="library-element-back" onClick={onBack}>← Zpět na plán stránky</button>
    <p className="element-context__what"><span className="element-context__kind">{context.kind}</span> {context.name}</p>
    <p className="element-context__where">{context.page}{context.box ? ` › ${context.box}` : " · celá stránka"}</p>
  </div>;
}
