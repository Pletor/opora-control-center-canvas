import { useState, type FormEvent } from "react";
import type { BoardRow } from "../logic/linie-board";
import { parentOf } from "../logic/linie-tree";

type Props = { rows: BoardRow[]; heads: string[]; onSubmit: (body: object) => Promise<boolean>; onClose: () => void };

const EMPTY = { title: "", essence: "", build: "", doneCriteria: "", branch: "", baseBranch: "", target: "" };
type Field = keyof typeof EMPTY;

/**
 * Nová kulička = zadání práce (`POST /work`): řádek (prázdný = server založí podle větve), název, podstata, stavba, kritéria hotovo (řádek = jedno kritérium),
 * jméno větve, výchozí větev a cíl. Větev se nezakládá; založí ji agent z výchozí větve. Zápis hlásí rodiči.
 */
export default function LinieWorkForm({ rows, heads, onSubmit, onClose }: Props) {
  const work = rows.filter((row) => !row.fixed && !row.auto && !row.git);
  const [rowId, setRowId] = useState("");
  const [form, setForm] = useState(EMPTY);
  // Dokud uživatel výchozí větev a cíl sám nezměnil, sledují rodiče odvozeného ze jména větve.
  const [touched, setTouched] = useState<Field[]>([]);
  const change = (key: Field, value: string) => {
    const next = { ...form, [key]: value };
    if (key === "branch") {
      const parent = parentOf(value, heads) ?? "";
      if (!touched.includes("baseBranch")) next.baseBranch = parent;
      if (!touched.includes("target")) next.target = parent;
    } else if (key === "baseBranch" || key === "target") setTouched([...touched, key]);
    setForm(next);
  };
  const set = (key: Field) => (event: { target: { value: string } }) => change(key, event.target.value);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const doneCriteria = form.doneCriteria.split("\n").map((line) => line.trim()).filter(Boolean);
    void onSubmit({ ...(rowId ? { rowId } : {}), ...form, doneCriteria, target: form.target.trim() || null }).then((ok) => { if (ok) { setForm(EMPTY); setTouched([]); onClose(); } });
  };
  const text = (key: Field, label: string, placeholder = "") => (
    <label className="pletor-dashboard__linie-field">{label}
      <input className="pletor-dashboard__input" value={form[key]} required={key !== "target" && key !== "baseBranch"} placeholder={placeholder} onChange={set(key)} />
    </label>
  );

  return (
    <form className="pletor-dashboard__linie-form" onSubmit={submit} aria-label="Nová kulička">
      <label className="pletor-dashboard__linie-field">řádek
        <select className="pletor-dashboard__input" value={rowId} onChange={(event) => setRowId(event.target.value)}>
          <option value="">(nový řádek podle větve)</option>
          {work.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
        </select>
      </label>
      <span className="pletor-dashboard__note">Řádek = větev; nová větev dostane vlastní řádek pod rodičem.</span>
      {text("title", "název", "např. Panel detailu karty")}
      {text("essence", "podstata (essence)")}
      {text("build", "co postavit (build)")}
      <label className="pletor-dashboard__linie-field">hotovo když (řádek = kritérium)
        <textarea className="pletor-dashboard__input" rows={3} value={form.doneCriteria} required onChange={set("doneCriteria")} />
      </label>
      {text("branch", "větev", "feat/…")}
      <span className="pletor-dashboard__note">feat/velin-linie-editor vzniká z feat/velin-linie a vrací se jen do ní.</span>
      {text("baseBranch", "výchozí větev (rodič)", "prázdné = odvodí server")}
      {text("target", "cíl", "prázdné = rodič")}
      <button type="submit" className="pletor-dashboard__button">Zadat kuličku</button>
      <button type="button" className="pletor-dashboard__button" onClick={onClose}>Zrušit</button>
    </form>
  );
}
