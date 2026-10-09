// Revize: historie fragmentů schránky s poznámkami (proč vznikla verze), nejnovější nahoře. Jen čtení.
import type { VaultNode } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { fold, shortWhen } from "../logic/vault-window-model";
import { historyUrl, useVaultGet, type HistoryItem, type VaultScope } from "../logic/vault-actions";

export default function HistorySection({ scope, vaultScope, roots, query }: { scope: VaultScope; vaultScope: string; roots: VaultNode[]; query: string }) {
  const { data, error } = useVaultGet<{ items: HistoryItem[] }>(historyUrl(scope, vaultScope), roots);
  if (error) return <p className="vault-window__error" role="alert">Historii nelze načíst: {error}</p>;
  if (!data) return <p className="vault-window__notice" role="status">Načítám historii…</p>;
  const items = data.items.filter((item) => !query.trim() || fold(item.title + " " + item.note).includes(fold(query.trim())));
  return (
    <div className="vault-stack" data-testid="vault-history">
      {items.length ? (
        <section className="vault-panel">
          {items.map((item) => (
            <div key={item.id + ":" + item.revision} className="vault-row">
              <span className="vault-row__side">{shortWhen(item.at)}</span>
              <span className="vault-row__side">{item.title.slice(0, 24)} r{item.revision}</span>
              <span className="vault-row__main">{item.deleted ? "Smazáno. " : ""}{item.note || "(bez poznámky)"}</span>
              <span className="vault-row__side">{item.actor === "human" ? "ty" : item.by}</span>
            </div>
          ))}
        </section>
      ) : <div className="vault-window__empty">{query ? "Hledání nenašlo žádnou revizi." : "Schránka zatím nemá žádnou revizi."}</div>}
    </div>
  );
}
