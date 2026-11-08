import { useState } from "react";

type Props = { disabled?: boolean; onConfirm: () => void };

/**
 * „Přijmout bez zkoušky“ (zkouška §7): vedlejší odkaz, který nejdřív v řádku zeptá, jestli člověk opravdu přijímá
 * revizi, kterou nezkoušel. Teprve „Ano, přijmout“ jde nahoru; „Zpět“ vrátí odkaz.
 */
export default function LinieUntested({ disabled, onConfirm }: Props) {
  const [asking, setAsking] = useState(false);
  if (!asking) return <button type="button" className="linie-trial__untested" disabled={disabled} onClick={() => setAsking(true)}>přijmout bez zkoušky</button>;
  return (
    <span className="linie-trial__confirm" role="group" aria-label="Potvrzení přijetí bez zkoušky">
      <span>Hlavu jsi nezkoušel. Opravdu přijmout?</span>
      <button type="button" className="linie-trial__untested linie-trial__untested--yes" onClick={() => { setAsking(false); onConfirm(); }}>Ano, přijmout</button>
      <button type="button" className="linie-trial__untested" onClick={() => setAsking(false)}>Zpět</button>
    </span>
  );
}
