// Vysouvací panel knihovny u levé hrany plátna: vyjede po kliknutí na kartu, obsah patří té kartě.
// V hlavě jsou záložky Bloky / Akce / Podklady / Kontext. Panel nic neukládá; každá změna bublá do App.
// Když je vybraný konkrétní blok, App pošle `content` a panel místo záložek ukáže jeho Editor.
import type { ReactNode } from "react";
import type { CanvasNode, GraphEdge } from "@/shared/types/logic/types";
import type { NodeWorkflowFull, PipelineLibrary, PipelineTemplate } from "@/shared/desktop-state/logic/types";
import type { CardBlockRow } from "@/editor/canvas/node-card/logic/card-model";
import MaterialsBlock, { type MaterialHandlers } from "@/editor/workflow/blocks/components/MaterialsBlock";
import LibraryContext from "@/editor/component-library/node-library/components/LibraryContext";
import { BLOCK_KINDS, LIBRARY_SECTIONS, type BlockKind, type LibrarySection } from "@/editor/component-library/node-library/logic/library-model";

export default function NodeLibraryDrawer({
  open,
  section,
  onSection,
  node,
  workflow,
  rows,
  readOnly,
  pipelines,
  edges,
  project,
  workspace,
  onClose,
  onAddBlock,
  onRemoveBlock,
  onAddAction,
  materials,
  content,
}: {
  open: boolean;
  section: LibrarySection;
  onSection: (section: LibrarySection) => void;
  node: CanvasNode | null;
  workflow: NodeWorkflowFull | null;
  rows: CardBlockRow[];
  readOnly: boolean;
  /** Vazby grafu pro kontrolu „Porty a vazby“ v sekci Kontext. */
  edges: GraphEdge[];
  /** Rozsah pro stažení balíčku pro model; jen čtení, nic se neodesílá. */
  project: string;
  workspace: string;
  pipelines: PipelineLibrary | null;
  onClose: () => void;
  onAddBlock: (kind: BlockKind) => void;
  onRemoveBlock: (blockId: string) => void;
  onAddAction: (pipeline: PipelineTemplate) => void;
  materials: MaterialHandlers;
  /** Editor vybraného bloku místo záložek; hlava panelu ukáže `content.title` a tělo `content.body`. */
  content?: { title: string; body: ReactNode };
}) {
  return (
    <aside className={"node-library" + (open ? " node-library--open" : "")} aria-label="Knihovna uzlu" aria-hidden={!open} data-testid="node-library-drawer">
      <header className="node-library__head">
        <strong className="node-library__title">{content ? content.title : node ? node.name : "Žádná karta"}</strong>
        <button type="button" className="node-library__close" aria-label="Zavřít knihovnu" onClick={onClose}>✕</button>
      </header>
      {!content && (
        <nav className="node-library__tabs" role="tablist" aria-label="Sekce knihovny">
          {LIBRARY_SECTIONS.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              className={"node-library__tab" + (section === item.id ? " node-library__tab--active" : "")}
              aria-selected={section === item.id}
              title={item.hint}
              data-testid={"library-tab-" + item.id}
              onClick={() => onSection(item.id)}
            >
              <span aria-hidden="true">{item.icon}</span> {item.label}
            </button>
          ))}
        </nav>
      )}
      <div className="node-library__body">
        {content ? content.body : !node || !workflow ? (
          <p className="node-library__empty">Klikněte na kartu na plátně. Knihovna pak nabídne bloky, akce a podklady pro ten uzel.</p>
        ) : section === "blocks" ? (
          <>
            <p className="node-library__note">Vložte blok obsahu do karty:</p>
            {BLOCK_KINDS.map((item) => (
              <button key={item.kind} type="button" className="node-library__pick" disabled={readOnly} data-testid={"library-kind-" + item.kind} onClick={() => onAddBlock(item.kind)}>
                <span className="node-library__pick-icon" aria-hidden="true">{item.icon}</span>
                <span className="node-library__pick-text"><strong>{item.label}</strong><small>{item.hint}</small></span>
              </button>
            ))}
            {rows.length > 0 && (
              <>
                <p className="node-library__note">V kartě je:</p>
                <ol className="node-library__rows">
                  {rows.map((row) => (
                    <li key={row.id} className="node-library__row">
                      <span className="node-library__row-number">{row.number}</span>
                      <span className="node-library__row-title">{row.title}</span>
                      <button type="button" className="node-library__row-remove" aria-label="Odebrat blok" disabled={readOnly} onClick={() => onRemoveBlock(row.id)}>✕</button>
                    </li>
                  ))}
                </ol>
              </>
            )}
          </>
        ) : section === "actions" ? (
          <>
            <p className="node-library__note">Klik přidá pipeline na konec výrobní linky uzlu ({workflow.actions.length} akcí).</p>
            {!pipelines && <p role="status" className="node-library__empty">Načítám knihovnu pipeline…</p>}
            {pipelines?.categories.length === 0 && <p className="node-library__empty">Knihovna pipeline je prázdná (library/pipelines.json).</p>}
            {pipelines?.categories.map((category) => (
              <section key={category.id} className="node-library__category">
                <h4 className="node-library__category-title">{category.label}</h4>
                <p className="node-library__note">{category.description}</p>
                {category.pipelines.map((p) => (
                  <button key={p.id} type="button" className="node-library__pick" disabled={readOnly} onClick={() => onAddAction(p)}>
                    <span className="node-library__pick-icon" aria-hidden="true">⚡</span>
                    <span className="node-library__pick-text"><strong>{p.label}</strong><small>{p.description}</small></span>
                  </button>
                ))}
              </section>
            ))}
          </>
        ) : section === "materials" ? (
          <div className="node-library__materials canvas-block block-material">
            <div className="block-body">
              <p className="block-note">Obrázky a odkazy, které agent dostane jako podklad:</p>
              <MaterialsBlock materials={workflow.materials} disabled={readOnly} readOnly={readOnly} {...materials} />
            </div>
          </div>
        ) : (
          <LibraryContext node={node} workflow={workflow} edges={edges} project={project} workspace={workspace} />
        )}
      </div>
    </aside>
  );
}
