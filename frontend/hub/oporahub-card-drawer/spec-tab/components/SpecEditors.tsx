import { useEffect, useMemo, useState } from "react";
import NodeSpecEditor from "@/editor/node-detail/assignment/components/NodeSpecEditor";
import NodeTextEditor from "@/editor/node-detail/content/components/NodeTextEditor";
import NodeCardEditor from "@/editor/node-detail/card-fields/components/NodeCardEditor";
import NodeLinksPanel from "@/editor/node-detail/links/components/NodeLinksPanel";
import BriefChips from "@/editor/node-detail/brief-vault/components/BriefChips";
import { useBriefVault } from "@/editor/node-detail/brief-vault/logic/use-brief-vault";
import { indexVault, scopeOfFragment } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import type { CanvasNode } from "@/shared/types/logic/types";
import type { DrawerEditor } from "../../logic/drawer-editor";

type Props = { project: string; workspace: string; node: CanvasNode; editor: DrawerEditor; onSpecSaved: (stored: { fields: unknown }) => void };

/** Účel komponenty je součást cíle: krátký dlouhodobý smysl uložený na uzlu, edituje se vedle zadání. */
function PurposeField({ node, editor }: { node: CanvasNode; editor: DrawerEditor }) {
  const [purpose, setPurpose] = useState(node.purpose);
  useEffect(() => setPurpose(node.purpose), [node.purpose]);
  const dirty = purpose !== node.purpose;
  return <label className="spec-tab__field">Účel komponenty (dlouhodobý smysl, doplňuje cíl)
    <textarea rows={3} maxLength={12000} value={purpose} readOnly={editor.readOnly} aria-label="Účel komponenty" onChange={event => setPurpose(event.target.value)} />
    {dirty && !editor.readOnly && <button type="button" className="spec-tab__ghost" disabled={editor.busy} onClick={() => editor.onSave({ ...node, purpose })}>Uložit účel</button>}
  </label>;
}

/** Ponechané editory karty ve sbalených oddílech: pracovní zadání, Schránka, popis, nastavení, vazby. */
export default function SpecEditors({ project, workspace, node, editor, onSpecSaved }: Props) {
  const vault = useBriefVault({ project, workspace }, editor.resultRevision);
  const index = useMemo(() => indexVault(vault.tree?.roots ?? []), [vault.tree]);
  const refs = editor.fragmentRefs(node.id);
  const openFragment = (fragmentId: string) => {
    const scope = scopeOfFragment(index, fragmentId);
    if (scope != null) editor.onOpenVault?.(scope, fragmentId);
  };
  const key = JSON.stringify([project, workspace, node.id]);
  return <div className="spec-tab__editors">
    <details className="spec-tab__fold" data-oh-fold="working-spec">
      <summary>Upravit pracovní zadání</summary>
      <p className="spec-tab__muted">Změny se ukládají do pracovní verze; přijatou mění jen přijatý návrh. Kroky plánu se mění stejnou cestou.</p>
      <NodeSpecEditor key={key} project={project} workspace={workspace} nodeId={node.id} disabled={editor.busy || editor.readOnly}
        refreshRevision={editor.specRefreshRevision} onStored={onSpecSaved} />
      <PurposeField node={node} editor={editor} />
    </details>
    {!!refs?.length && <details className="spec-tab__fold" data-oh-fold="brief-vault">
      <summary>Schránka · podklady karty</summary>
      <BriefChips refs={refs} index={index} onOpen={editor.onOpenVault ? openFragment : undefined} />
    </details>}
    <details className="spec-tab__fold" data-oh-fold="text">
      <summary>Popis a podklady</summary>
      <NodeTextEditor key={key} project={project} workspace={workspace} node={node.id} />
    </details>
    {node.kind === "node" && <details className="spec-tab__fold" data-oh-fold="card-fields">
      <summary>Nastavení karty</summary>
      <NodeCardEditor node={node} readOnly={editor.readOnly} busy={editor.busy} onSave={editor.onSave} />
    </details>}
    <details className="spec-tab__fold" data-oh-fold="links">
      <summary>Vazby a souvislosti</summary>
      <NodeLinksPanel project={project} workspace={workspace} node={node.id} revision={0} readOnly={editor.readOnly} onOpenNode={editor.onOpenNode} />
    </details>
  </div>;
}
