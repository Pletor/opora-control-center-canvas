// Vstup do schránky (návrh Claude Design „Card“): v záložce Schránka u sektoru či karty a v inspektoru
// plátna/vrstvy jen pruh pokrytí, jedna věta souhrnu a tlačítko „Otevřít schránku“ (okno s levým menu).
import { coverageOf, type VaultNode } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import CoverageBar, { chaptersLabel } from "@/editor/node-detail/brief-vault/components/CoverageBar";
import "@/editor/node-detail/brief-vault-window/styles/brief-vault-window.css";

function count(roots: VaultNode[], kind: "research" | "question"): number {
  let total = 0;
  const stack = [...roots];
  while (stack.length) {
    const node = stack.pop()!;
    if (node.kind === kind && !(kind === "question" && node.question?.answered)) total += 1;
    stack.push(...node.children);
  }
  return total;
}

export default function BriefVaultEntry({ roots, loading, error, readOnly, onOpen }: {
  roots: VaultNode[];
  loading: boolean;
  error: string;
  readOnly: boolean;
  onOpen: () => void;
}) {
  if (loading) return <p className="muted" role="status">Načítám schránku…</p>;
  const coverage = coverageOf(roots);
  const cards = coverage.inserted + coverage.mvpInserted + coverage.changed;
  const research = count(roots, "research");
  const questions = count(roots, "question");
  return (
    <div className="vault-entry" data-testid="brief-vault-entry">
      {error && <p className="error" role="alert">Schránku nelze načíst: {error}</p>}
      {readOnly ? <p className="vault-entry__summary">Main je jen ke čtení; schránka žije v pracovním prostoru.</p>
        : roots.length ? (
          <>
            <CoverageBar coverage={coverage} legend={false} />
            <p className="vault-entry__summary">
              {coverage.leaves} {chaptersLabel(coverage.leaves)} · {cards} jako karty · {research} {research === 1 ? "výzkum" : research >= 2 && research <= 4 ? "výzkumy" : "výzkumů"} · {questions} k upřesnění
              {coverage.changed > 0 && <> · <span className="brief-vault__changed">⚠ {coverage.changed} změněno po vložení</span></>}
            </p>
          </>
        ) : <p className="vault-entry__summary">Schránka je zatím prázdná: zadání sem vloží agent, Podněty a rozhodnutí karet uvidíš i tak.</p>}
      <button type="button" className="vault-button vault-button--primary" onClick={onOpen} disabled={readOnly}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M4 7h16v13H4zM4 7l2-3h12l2 3M9 12h6" /></svg>
        Otevřít schránku
      </button>
    </div>
  );
}
