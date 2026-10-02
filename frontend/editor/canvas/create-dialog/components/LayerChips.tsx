// Vrstva karty jako jedna řada malých čipů FE · BE · DB · Knihovna (otázky frontend / backend /
// database / library z docs/pravidla-struktury.md). Vrstva je nepovinná: druhý klik na vybraný čip
// výběr zruší. Dílek nic neukládá; každou změnu ohlásí celou rozepsanou kartu nahoru přes onChange.
// Používá ho pop-up tvorby i detail karty, aby se vrstva volila všude stejně.
import { useId } from "react";
import { toggleLayer, type CardDraft } from "@/editor/canvas/create-dialog/logic/card-draft";
import { CARD_LAYERS, LAYER_LABEL } from "@/shared/card-context/logic/card-context";
import "@/editor/canvas/create-dialog/styles/create-dialog.css";

const LAYER_TITLE: Record<string, string> = {
  frontend: "Frontend: co uživatel vidí a ovládá",
  backend: "Backend: API a logika prostředí",
  database: "Databáze: co se ukládá a jak",
  library: "Knihovna: sdílený kód bez vlastního prostředí",
};

export default function LayerChips({
  value,
  disabled = false,
  onChange,
}: {
  value: CardDraft;
  disabled?: boolean;
  onChange: (next: CardDraft) => void;
}) {
  const labelId = useId();
  return (
    <div className="create-dialog__group">
      <span className="create-dialog__label" id={labelId}>Vrstva <span className="create-dialog__optional">(nepovinné)</span></span>
      <div className="create-dialog__chips" role="radiogroup" aria-labelledby={labelId}>
        {CARD_LAYERS.map((layer) => {
          const on = value.layer === layer;
          return (
            <button
              key={layer}
              type="button"
              role="radio"
              aria-checked={on}
              title={LAYER_TITLE[layer]}
              disabled={disabled}
              className={"create-dialog__chip" + (on ? " create-dialog__chip--on" : "")}
              onClick={() => onChange(toggleLayer(value, layer))}
            >
              {LAYER_LABEL[layer]}
            </button>
          );
        })}
      </div>
    </div>
  );
}
