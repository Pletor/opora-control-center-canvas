import { CONNECTOR_STATUS_LABEL, CONNECTORS } from "@/settings/logic/connectors";

/** Seznam aplikací k napojení. Zatím jen katalog; tlačítko Napojit se aktivuje, až konektor existuje. */
export default function ConnectorsSection() {
  return (
    <section className="settings-section" aria-labelledby="connectors-title">
      <h3 id="connectors-title">Connectors</h3>
      <p className="muted">Aplikace, které Opora napojí. Napojení je vždy výslovné, nic se nespouští samo.</p>
      <ul className="connectors">
        {CONNECTORS.map((item) => (
          <li key={item.id} className="connector">
            <div className="connector-body">
              <strong>{item.name}</strong>
              <span>{item.purpose}</span>
            </div>
            <span className={"connector-status " + item.status}>{CONNECTOR_STATUS_LABEL[item.status]}</span>
            <button type="button" disabled={item.status !== "available"} title={item.status === "available" ? "Napojit" : "Napojení zatím není k dispozici"}>
              Napojit
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
