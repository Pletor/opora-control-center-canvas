import { useState } from "react";
import type { NodeTypeSpec } from "../../logic/flow-types";
import { LAYER_BADGE } from "../../flow-lanes/logic/layers";
import { INTENTS, intentOptions } from "../logic/intents";

type Props = { types: readonly NodeTypeSpec[]; onPick: (type: string) => void; onClose: () => void };

/** Dialog „Co chci udělat?“: člověk vybere záměr a průvodce nabídne typy uzlů s odpovídajícím štítkem, každý s větou
 * „kdy použít“. Klik na typ vloží uzel stejně jako v paletě. Deterministické, bez modelu. */
export default function IntentWizard({ types, onPick, onClose }: Props) {
  const [intent, setIntent] = useState<string | null>(null);
  const options = intent ? intentOptions(types, intent) : [];
  return <div className="node-palette__wizard" role="dialog" aria-label="Co chci udělat?" data-testid="intent-wizard">
    <header className="node-palette__head">
      <h4 className="node-palette__title">Co chci udělat?</h4>
      <button type="button" className="node-palette__close" aria-label="Zavřít průvodce" onClick={onClose}>×</button>
    </header>
    {!intent ? <div className="node-palette__intents">
      {INTENTS.map((item) => <button key={item.id} type="button" className="node-palette__intent" data-testid={`intent-${item.id}`} onClick={() => setIntent(item.id)}>{item.label}</button>)}
    </div> : <>
      <button type="button" className="node-palette__port-clear" onClick={() => setIntent(null)}>← jiný záměr</button>
      {!options.length && <p className="node-palette__empty">Pro tento záměr registr zatím nemá žádný typ.</p>}
      {options.map((option) => <button key={option.type} type="button" className="node-palette__item" data-testid={`intent-pick-${option.type}`} onClick={() => onPick(option.type)}>
        {option.layer && <span className={`node-palette__layer node-palette__layer--${option.layer}`}>{LAYER_BADGE[option.layer]}</span>}
        <span className="node-palette__text"><b className="node-palette__name">{option.type}</b><small className="node-palette__use">{option.use}</small></span>
      </button>)}
    </>}
  </div>;
}
