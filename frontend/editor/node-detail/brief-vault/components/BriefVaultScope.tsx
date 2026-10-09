// Schránka plátna nebo otevřené vrstvy v inspektoru bez výběru: načte strom a ukáže kořeny daného rozsahu.
import { useBriefVault } from "@/editor/node-detail/brief-vault/logic/use-brief-vault";
import { rootsOf } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import BriefVaultPanel from "@/editor/node-detail/brief-vault/components/BriefVaultPanel";

export default function BriefVaultScope({ project, workspace, scope, scopeLabel, revision, nodeNames, onOpenNode }: {
  project: string;
  workspace: string;
  /** `""` = plátno, jinak id sektoru otevřené vrstvy. */
  scope: string;
  scopeLabel: string;
  revision: unknown;
  nodeNames: Record<string, string>;
  onOpenNode: (id: string) => void;
}) {
  const vault = useBriefVault({ project, workspace }, revision);
  return (
    <BriefVaultPanel project={project} workspace={workspace} roots={rootsOf(vault.tree?.roots ?? [], scope)}
      loading={!vault.tree && !vault.error} readOnly={!!vault.tree?.readOnly} error={vault.error}
      scopeLabel={scopeLabel} nodeNames={nodeNames} onOpenNode={onOpenNode} />
  );
}
