// Původ zdroje nové karty a pole, která k němu patří: myšlenka nic dalšího nechce (popis je pod tím),
// existující zdroj ukáže strom zdrojů projektu a nový návrh zamýšlenou cestu s přepínačem Složka /
// Soubor na jednom řádku. Dílek drží jen zobrazení; každou změnu formuláře hlásí nahoru přes onChange
// a pravidla (co je povolené) dostává hotová v `rules`.
import SourceExplorer from "@/project/source-tree/components/SourceExplorer";
import OriginSwitch from "@/editor/canvas/create-dialog/components/OriginSwitch";
import { chooseOrigin, type CreateForm, type CreateRules, type EntryKind } from "@/editor/canvas/create-dialog/logic/create-form";

const ENTRY_KINDS: { kind: EntryKind; label: string }[] = [
  { kind: "directory", label: "Složka" },
  { kind: "file", label: "Soubor" },
];

export default function CreateSourceFields({
  form,
  rules,
  project,
  workspace,
  onChange,
}: {
  form: CreateForm;
  rules: CreateRules;
  project: string;
  workspace: string;
  onChange: (next: CreateForm) => void;
}) {
  const sector = form.kind === "sector";
  const set = (patch: Partial<CreateForm>) => onChange({ ...form, ...patch });
  return (
    <>
      <OriginSwitch form={form} rules={rules} onChoose={(origin) => onChange(chooseOrigin(form, origin))} />
      {form.origin === "existing" && (
        rules.existingAllowed ? (
          <>
            <div className="create-source-picker">
              <SourceExplorer
                project={project}
                workspace={workspace}
                selected={form.path ?? ""}
                onSelect={(path, kind) => set(sector ? { path } : { path, entryKind: kind === "root" ? "directory" : kind })}
                search=""
                refresh={0}
                basePath={sector ? "" : (rules.effectiveSector?.sourceRef?.path ?? "")}
                rootLabel=""
                directoriesOnly={sector}
                rootOnly={sector}
              />
            </div>
            {form.path !== null ? (
              <p className="create-source-picked">Vybráno: <code>{form.path || "/"}</code></p>
            ) : (
              <p className="create-source-note">Vyberte {sector ? "složku" : "složku nebo soubor"} ve stromu.</p>
            )}
          </>
        ) : (
          <p className="create-source-note">Tento sektor nemá napojený existující zdroj; nejdřív mu jej přiřaďte, nebo uzel jen navrhněte.</p>
        )
      )}
      {form.origin === "planned" && (
        <div className="create-dialog__row">
          <label className="field create-dialog__grow">
            {sector ? "Zamýšlená cesta (nepovinné)" : rules.effectiveSector?.sourceRef ? "Zamýšlená cesta v sektoru (nepovinné)" : "Zamýšlená cesta v projektu (nepovinné)"}
            <input aria-label="Zamýšlená cesta" value={form.plannedPath} maxLength={400}
              placeholder="nic se nevytváří na disku" onChange={(e) => set({ plannedPath: e.target.value })} />
          </label>
          {!sector && (
            <div className="create-dialog__chips create-dialog__chips--inline" role="radiogroup" aria-label="Druh navrhovaného zdroje">
              {ENTRY_KINDS.map((entry) => (
                <button
                  key={entry.kind}
                  type="button"
                  role="radio"
                  aria-checked={form.entryKind === entry.kind}
                  className={"create-dialog__chip" + (form.entryKind === entry.kind ? " create-dialog__chip--on" : "")}
                  onClick={() => set({ entryKind: entry.kind })}
                >
                  {entry.label}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </>
  );
}
