import type { ComponentProps, ReactNode } from "react";
import ProjectTree from "../project-tree/components/ProjectTree";

/** Levý sloupec plátna 2: nahoře Struktura otevřené domény, pod ní paleta podle vrstvy (boxy layoutu nebo prvky logiky). */
export default function PageSidebar({ tree, palette }: { tree: ComponentProps<typeof ProjectTree>; palette: ReactNode }) {
  return <aside className="page-editor__sidebar">
    <ProjectTree {...tree}/>
    {palette}
  </aside>;
}
