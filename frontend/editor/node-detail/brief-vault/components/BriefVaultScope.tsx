// Schránka plátna nebo otevřené vrstvy v inspektoru bez výběru: pruh pokrytí a tlačítko „Otevřít schránku“
// (okno s levým menu otevře rodič přes onOpenVault).
import { useBriefVault } from "@/editor/node-detail/brief-vault/logic/use-brief-vault";
import { rootsOf } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import BriefVaultEntry from "@/editor/node-detail/brief-vault/components/BriefVaultEntry";

export default function BriefVaultScope({ project, workspace, scope, revision, onOpenVault }: {
  project: string;
  workspace: string;
  /** `""` = plátno, jinak id sektoru otevřené vrstvy. */
  scope: string;
  revision: unknown;
  onOpenVault: (scope: string) => void;
}) {
  const vault = useBriefVault({ project, workspace }, revision);
  return (
    <BriefVaultEntry roots={rootsOf(vault.tree?.roots ?? [], scope)} loading={!vault.tree && !vault.error}
      readOnly={!!vault.tree?.readOnly} error={vault.error} onOpen={() => onOpenVault(scope)} />
  );
}
