// Zpětná vazba: co člověk řekl k výzkumu a výsledkům (souhlas · nesouhlas · komentář). Agent to dostane
// v dalším kole v balíčku research-brief. Append-only, jen zobrazení.
import type { Feedback, VaultNode } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { flatten } from "../logic/vault-window-model";
import { FeedbackList } from "./FeedbackBox";

export default function FeedbackSection({ roots, feedback, query }: { roots: VaultNode[]; feedback: Feedback[]; query: string }) {
  const titles = Object.fromEntries(flatten(roots).map((item) => [item.node.id, item.node.title]));
  const needle = query.trim().toLocaleLowerCase("cs");
  const items = feedback.filter((item) => !needle || (item.text + " " + (titles[item.fragmentId] ?? "")).toLocaleLowerCase("cs").includes(needle));
  return (
    <div className="vault-stack" data-testid="vault-feedback">
      <p className="vault-window__lead">Co jsi k výzkumu a výsledkům řekl. Agent to dostane v dalším kole jako vstup.</p>
      {items.length ? <section className="vault-panel"><FeedbackList items={items} titles={titles} /></section>
        : <div className="vault-window__empty">Zatím žádná zpětná vazba. Dáš ji u výzkumu (Souhlasím · Nesouhlasím · komentář); zapisuje jen člověk.</div>}
    </div>
  );
}
