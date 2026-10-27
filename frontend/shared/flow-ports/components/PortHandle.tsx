// Úchyt portu: React Flow `Handle` s jednotným vzhledem (neviditelná zásahová plocha 26 px, kulička 10 px),
// českým názvem v `title` / `aria-label` / tooltipu a tabulátorem. Vzhled řídí `styles/flow-ports.css`;
// barvu kuličky dodává volající třídou přes `--port-fill` / `--port-ring`. Dílek nic neukládá.
import { Handle, type HandleProps } from "@xyflow/react";
import type { ComponentProps } from "react";
import { portLabel, portTitle, type PortKind } from "@/shared/flow-ports/logic/port-labels";
import "@/shared/flow-ports/styles/flow-ports.css";

type Props = HandleProps & Omit<ComponentProps<"div">, "id" | "children"> & {
  kind: PortKind;
  /** Jméno portu bloku; ostatní druhy mají pevný název. */
  name?: string;
  /** Co s portem jde dělat; připojí se za název do `title`. */
  hint?: string;
};

export default function PortHandle({ kind, name, hint, className = "", ...rest }: Props) {
  const label = portLabel(kind, name);
  return (
    <Handle
      {...rest}
      className={`flow-port ${className}`.trim()}
      title={portTitle(kind, name, hint)}
      aria-label={label}
      data-port-label={label}
      tabIndex={0}
    />
  );
}
