import type { CSSProperties } from "react";
import type { ConnectorView } from "@/hub/oporahub-agent-state/logic/loop-model";

/** Šipka mezi etapami s tím, co po ní teče (hlava, SHA…); přerušená, když druhý konec není napojen. */
export default function LoopConnector({ connector }: { connector: ConnectorView }) {
  const place = { "--oh-row": connector.row, "--oh-col": connector.col } as CSSProperties;
  return <div className={`oporahub-loop__link oporahub-loop__link--${connector.dir} oporahub-loop__link--${connector.tone}`} style={place}
    data-oh-link={`${connector.from}->${connector.to}`} data-oh-link-state={connector.tone} aria-hidden="true">
    <span className="oporahub-loop__line" /><span className="oporahub-loop__link-label">{connector.label}</span>
  </div>;
}
