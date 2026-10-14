import { useState } from "react";
import type { TreeGroup } from "../project-tree/logic/project-tree-model";
import ProjectTree from "../project-tree/components/ProjectTree";
import ArchitectureCatalog from "./ArchitectureCatalog";
import PageIcon from "./PageIcon";

type Props = {
  /** `disabled` locks the library (page content); `treeDisabled` locks adding pages (structure). */
  projectName: string; groups: TreeGroup[]; scopeName: string; disabled: boolean; treeDisabled: boolean;
  onOpenPage: (domainId: string, pageId: string) => void; onAddPage: (domainId: string) => void; onInsert: (id: string) => void;
};

/** Left column: tabs switch between project navigation and the element library. */
export default function PageSidebar({ projectName, groups, scopeName, disabled, treeDisabled, onOpenPage, onAddPage, onInsert }: Props) {
  const [side, setSide] = useState<"tree" | "library">("tree");
  return <aside className="page-editor__sidebar">
    <div className="page-editor__tabs" role="tablist" aria-label="Levý panel">
      <button type="button" role="tab" aria-selected={side === "tree"} className="page-editor__tab" data-testid="architecture-tree-tab" onClick={() => setSide("tree")}>
        <PageIcon name="tree" size={15}/>Strom projektu</button>
      <button type="button" role="tab" aria-selected={side === "library"} className="page-editor__tab" data-testid="architecture-library-tab" onClick={() => setSide("library")}>
        <PageIcon name="library" size={15}/>Knihovna prvků</button>
    </div>
    <div role="tabpanel" hidden={side !== "tree"}>
      <ProjectTree title={projectName} groups={groups} disabled={treeDisabled} onOpenPage={onOpenPage} onAddPage={onAddPage}/>
    </div>
    <div role="tabpanel" hidden={side !== "library"}>
      <ArchitectureCatalog disabled={disabled} scopeName={scopeName} onInsert={onInsert}/>
    </div>
  </aside>;
}
