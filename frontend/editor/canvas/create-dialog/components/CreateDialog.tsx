// Pop-up tvorby sektoru a uzlu (docs/kontext-karet-a-index.md §7). Rodič dílků, čtený shora dolů:
// název, u uzlu mimo sektor cílový sektor, u uzlu vrstva (čipy), původ (segmentový přepínač), pole
// podle původu, jeden popis a sbalené nepovinné sekce (zadání sektoru / pro agenta). Rozepsaný
// formulář drží u sebe; hotový uzel a zadání ohlásí přes onCreate. Nic neukládá — to dělá App.
import { useState } from "react";
import { useScopedSaveParticipant } from "@/shared/hooks/logic/save-scope-context";
import AgentFields from "@/editor/canvas/create-dialog/components/AgentFields";
import CreateSourceFields from "@/editor/canvas/create-dialog/components/CreateSourceFields";
import FoldSection from "@/editor/canvas/create-dialog/components/FoldSection";
import LayerChips from "@/editor/canvas/create-dialog/components/LayerChips";
import PurposeField from "@/editor/canvas/create-dialog/components/PurposeField";
import SectorSpecFields from "@/editor/canvas/create-dialog/components/SectorSpecFields";
import { agentSummary } from "@/editor/canvas/create-dialog/logic/card-draft";
import {
  buildCreated,
  canCreate,
  changeTargetSector,
  createRules,
  emptyCreateForm,
  missingFields,
  nameLabel,
  showsPurpose,
  specSummary,
  type CreateContext,
  type CreateKind,
  type CreateResult,
} from "@/editor/canvas/create-dialog/logic/create-form";
import type { CanvasNode } from "@/shared/types/logic/types";
import "@/editor/canvas/create-dialog/styles/create-dialog.css";

type SectorOption = Pick<CanvasNode, "id" | "name" | "sourceRef">;

export default function CreateDialog({
  kind,
  project,
  workspace,
  parent,
  nodes,
  ancestorSector,
  sectors,
  legacyFree,
  busy,
  onCreate,
}: {
  kind: CreateKind;
  project: string;
  workspace: string;
  /** Vrstva, ve které dialog vznikl; uzel bez sektoru ve vrstvě jde do vybraného cílového sektoru. */
  parent: string | null;
  nodes: Pick<CanvasNode, "parentId">[];
  /** Sektor, ve kterém vrstva leží (nejbližší předek druhu sektor), nebo null. */
  ancestorSector: SectorOption | null;
  sectors: SectorOption[];
  /** Schopnost projektu z `project-capabilities`; dialog druh projektu nezná. */
  legacyFree: boolean;
  busy: boolean;
  onCreate: (result: CreateResult) => void;
}) {
  const [form, setForm] = useState(() => emptyCreateForm(kind));
  useScopedSaveParticipant({
    id: `create-dialog:${kind}:${parent ?? "root"}`,
    label: kind === "sector" ? "Nový sektor" : "Nový uzel",
    dirty: JSON.stringify(form) !== JSON.stringify(emptyCreateForm(kind)),
    pending: busy,
    blocked: "Rozpracovanou kartu nejprve vytvořte nebo její formulář zavřete. Uložit vše nové karty samo nevytváří.",
  });
  const targetSector = sectors.find((s) => s.id === form.targetSector) ?? null;
  const ctx: CreateContext = { ancestorSector, targetSector, legacyFree };
  const rules = createRules(form, ctx);
  const missing = missingFields(form, ctx);
  const ready = canCreate(form, ctx);
  const sector = kind === "sector";
  const showTarget = !sector && !ancestorSector && (!rules.concept || sectors.length > 0);
  return (
    <form
      className="create-dialog"
      onSubmit={(e) => {
        e.preventDefault();
        if (busy || !ready) return;
        onCreate(buildCreated(form, ctx, { parent, nodes, id: crypto.randomUUID() }));
      }}
    >
      <header className="create-dialog__head">
        <div className="eyebrow">{sector ? "SEKTOR V TÉTO VRSTVĚ" : "UZEL V TÉTO VRSTVĚ"}</div>
        <h2>{sector ? "Nový sektor" : "Nový uzel"}</h2>
      </header>
      <label className="field">
        Název
        <input aria-label={nameLabel(kind)} value={form.name} required maxLength={160} autoFocus
          onChange={(e) => setForm({ ...form, name: e.target.value })} />
      </label>
      {showTarget && (
        <label className="field">
          Cílový sektor
          <select
            aria-label="Cílový sektor"
            value={form.targetSector}
            onChange={(e) => setForm(changeTargetSector(form, sectors.find((s) => s.id === e.target.value) ?? null, legacyFree))}
          >
            <option value="">{legacyFree ? "Bez zdroje (volný uzel jako dosud)" : "Vyberte sektor"}</option>
            {sectors.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          {rules.requiresTargetSector && !targetSector && (
            <p className="create-source-note">Tento projekt vyžaduje sektor. Vyberte cílový sektor, aby se uzel vytvořil v jeho vrstvě se zdrojovým kontextem.</p>
          )}
        </label>
      )}
      {!sector && <LayerChips value={form.card} onChange={(card) => setForm({ ...form, card })} />}
      {rules.requiresModeChoice && (
        <CreateSourceFields form={form} rules={rules} project={project} workspace={workspace} onChange={setForm} />
      )}
      {showsPurpose(form, rules) && (
        <PurposeField form={form} rules={rules} onChange={(purpose) => setForm({ ...form, purpose })} />
      )}
      {sector ? (
        <FoldSection title="Zadání sektoru (nepovinné)" summary={specSummary(form.spec)}>
          <SectorSpecFields value={form.spec} onChange={(spec) => setForm({ ...form, spec })} />
        </FoldSection>
      ) : (
        <FoldSection title="Pro agenta (nepovinné)" summary={agentSummary(form.card)}>
          <AgentFields value={form.card} onChange={(card) => setForm({ ...form, card })} />
        </FoldSection>
      )}
      <footer className="create-dialog__foot">
        <button className="primary create-dialog__submit" disabled={busy || !ready}>
          Vytvořit
        </button>
        {!ready && missing.length > 0 && (
          <p className="create-dialog__missing" role="status" data-testid="create-missing">
            Chybí: {missing.join(" · ")}
          </p>
        )}
      </footer>
    </form>
  );
}
