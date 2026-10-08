// Tlačítko ULOŽIT na pravém konci lišty Editoru. Nic neukládá samo: dostane, jestli je plátno od
// poslední verze změněné a jestli se právě ukládá, a klik hlásí nahoru (App volá totéž co Ctrl+S).
import { saveButtonView } from "@/editor/canvas/save-versions/logic/save-versions";

export default function SaveButton({ dirty, saving, disabled, onSave }: {
  dirty: boolean;
  saving: boolean;
  disabled: boolean;
  onSave: () => void;
}) {
  const view = saveButtonView(dirty, saving);
  return (
    <button type="button" className={"save-versions__save" + (view.dirty ? " save-versions__save--dirty" : "")}
      title={"Uložit rozepsaný obsah a vytvořit úplnou verzi pracovního prostoru (Ctrl+S)"} disabled={disabled || saving} onClick={onSave} data-testid="save-version">
      {view.dirty && !saving && <span className="save-versions__dot" aria-hidden="true" />}
      <svg className="save-versions__icon" viewBox="0 0 16 16" aria-hidden="true">
        <path d="M3 2.5h8l2.5 2.5v8.5H2.5v-11z M5 2.5v3.5h5V2.5 M4.5 13.5V9.5h7v4" />
      </svg>
      {saving ? view.label : "Uložit vše"}
      {view.dirty && <span className="save-versions__sr">, neuložené změny</span>}
    </button>
  );
}
