import type { ScaleKind, Theme, TokenFamily } from "@/project/site-admin/logic/site-document";
import { freeName } from "@/project/site-admin/logic/token-names";
import { addScaleToken, removeScaleToken, scaleFamily, SCALE_BASE, SCALE_LIMIT, updateScaleToken, withNote } from "../logic/scale-tokens";
import ScaleTokenRow from "./ScaleTokenRow";
import "../styles/ds-scale.css";

const EMPTY: Record<ScaleKind, string> = {
  spacing: "Zatím žádné mezery. Škála od jedné základní jednotky (4px base) drží rytmus celého webu.",
  radius: "Zatím žádná zaoblení. Dvě až tři hodnoty a pilulka (9999px) obvykle stačí.",
  shadow: "Zatím žádné stíny. Jeden stín na úroveň elevace; v tmavém tématu často „none“.",
};

/** Spacing, Corner radius nebo Shadows: poznámka rodiny a tokeny s ukázkou. Rodinu dostane hotovou a změnu hlásí
 *  celou rodinou nahoru; jména kontroluje proti celému systému. */
export default function ScaleSection({ kind, family: raw, themes, taken, onChange }: {
  kind: ScaleKind; family: TokenFamily | undefined; themes: Theme[]; taken: string[]; onChange: (family: TokenFamily) => void;
}) {
  const family = scaleFamily(raw);
  return <div className="ds-scale">
    <label className="ds-scale__note">Poznámka rodiny
      <input className="ds-scale__input" value={family.note ?? ""} maxLength={400} placeholder={kind === "spacing" ? "4px base" : kind === "radius" ? "Měkké, nikdy kulaté – kromě pilulek" : "Jedna úroveň na vrstvu"}
        onChange={(event) => onChange(withNote(family, event.target.value))}/>
    </label>
    {!family.tokens.length && <p className="ds-scale__empty">{EMPTY[kind]}</p>}
    {family.tokens.map((token, index) => <ScaleTokenRow key={index + ":" + token.name} kind={kind} token={token} themes={themes} taken={taken}
      onChange={(next) => onChange(updateScaleToken(family, index, next))} onRemove={() => onChange(removeScaleToken(family, index))}/>)}
    <button type="button" className="ds-scale__add" disabled={family.tokens.length >= SCALE_LIMIT}
      onClick={() => onChange(addScaleToken(family, kind, freeName(SCALE_BASE[kind].name, taken)))}>+ Přidat token</button>
  </div>;
}
