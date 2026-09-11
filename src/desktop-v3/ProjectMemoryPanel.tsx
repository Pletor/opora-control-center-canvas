import { useRef, useState } from "react";
import { useDesktopState } from "./state-store";
import type { Rule, RuleScope, Decision, Setting } from "./types";

function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `id-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function scopeLabel(rule: Rule): string {
  if (rule.scope === "project") return "celý projekt";
  if (rule.scope === "path") return `cesta ${rule.target}`;
  return `uzel ${rule.target}`;
}

export function ProjectMemoryPanel({
  project,
  workspace,
  path,
}: {
  project: string;
  workspace: string;
  path: string;
}) {
  const { state, readOnly, loading, error, reload, mutate } = useDesktopState(project, workspace);
  const [newSettingKey, setNewSettingKey] = useState("");
  const [newSettingValue, setNewSettingValue] = useState("");
  const [newRuleText, setNewRuleText] = useState("");
  const [newRuleScope, setNewRuleScope] = useState<RuleScope>("project");
  const [newDecisionText, setNewDecisionText] = useState("");
  const [busy, setBusy] = useState(false);

  // Identifies which project/workspace a pending write belongs to, so a late-arriving response
  // for a scope the user has since navigated away from can never clear a draft newly typed
  // elsewhere.
  const scope = `${project}::${workspace}`;
  const scopeRef = useRef(scope);
  scopeRef.current = scope;

  async function run(fn: (current: typeof state) => typeof state): Promise<boolean> {
    setBusy(true);
    const ok = await mutate(fn);
    setBusy(false);
    return ok;
  }

  function editSetting(id: string, value: string) {
    return run((current) => ({
      ...current,
      settings: current.settings.map((s) => (s.id === id ? { ...s, value } : s)),
    }));
  }

  function removeSetting(id: string) {
    return run((current) => ({ ...current, settings: current.settings.filter((s) => s.id !== id) }));
  }

  function addSetting() {
    if (busy) return;
    const key = newSettingKey.trim();
    if (!key) return;
    const value = newSettingValue.trim();
    const setting: Setting = { id: newId(), key, value };
    const requestScope = scopeRef.current;
    run((current) => ({ ...current, settings: current.settings.concat([setting]) })).then((ok) => {
      if (ok && scopeRef.current === requestScope) {
        setNewSettingKey("");
        setNewSettingValue("");
      }
    });
  }

  function addRule() {
    if (busy) return;
    const raw = newRuleText.trim();
    if (!raw) return;
    const negative = /^ne\s*:/i.test(raw);
    const text = negative ? raw.replace(/^ne\s*:\s*/i, "") : raw;
    const target = newRuleScope === "path" ? path : "";
    if (newRuleScope === "path" && !path) return;
    const rule: Rule = { id: newId(), text, kind: negative ? "must_not" : "must", scope: newRuleScope, target };
    const requestScope = scopeRef.current;
    run((current) => ({ ...current, rules: current.rules.concat([rule]) })).then((ok) => {
      if (ok && scopeRef.current === requestScope) setNewRuleText("");
    });
  }

  function removeRule(id: string) {
    return run((current) => ({ ...current, rules: current.rules.filter((r) => r.id !== id) }));
  }

  function addDecision() {
    if (busy) return;
    const text = newDecisionText.trim();
    if (!text) return;
    const decision: Decision = {
      id: newId(),
      text,
      pinned: true,
      path: path || "",
      nodeId: "",
      createdAt: new Date().toISOString(),
      by: "human",
    };
    const requestScope = scopeRef.current;
    run((current) => ({ ...current, decisions: [decision].concat(current.decisions) })).then((ok) => {
      if (ok && scopeRef.current === requestScope) setNewDecisionText("");
    });
  }

  function togglePin(id: string) {
    return run((current) => ({
      ...current,
      decisions: current.decisions.map((d) => (d.id === id ? { ...d, pinned: !d.pinned } : d)),
    }));
  }

  const pinnedCount = state.decisions.filter((d) => d.pinned).length;
  const sortedDecisions = state.decisions
    .slice()
    .sort((a, b) => (a.createdAt < b.createdAt ? 1 : a.createdAt > b.createdAt ? -1 : 0));

  return (
    <section className="v3-panel v3-project-memory" aria-label="Paměť projektu">
      <header className="v3-panel-head">
        <h2>Paměť projektu</h2>
        <p className="v3-note">
          Nastavení, pravidla a rozhodnutí, které agent dostane s balíčkem úkolu. Prázdné je výchozí stav — žádná
          demo data.
        </p>
        {readOnly && <p role="status" className="v3-readonly">Main je pouze pro čtení; změny se neuloží.</p>}
      </header>
      {loading && <p role="status">Načítám paměť projektu…</p>}
      {error && (
        <p role="alert" className="v3-error">
          {error}{" "}
          <button type="button" onClick={reload}>
            Znovu načíst
          </button>
        </p>
      )}
      {!loading && (
        <>
          <section className="v3-section" aria-label="Nastavení projektu">
            <h3>Nastavení</h3>
            {state.settings.length === 0 && <p className="v3-empty">Zatím žádná nastavení.</p>}
            <ul className="v3-kv-list">
              {state.settings.map((setting) => (
                <li key={setting.id} className="v3-kv-row">
                  <span className="v3-kv-key">{setting.key}</span>
                  <input
                    aria-label={`Hodnota ${setting.key}`}
                    value={setting.value}
                    disabled={readOnly || busy}
                    onChange={(e) => editSetting(setting.id, e.target.value)}
                  />
                  <button type="button" disabled={readOnly || busy} onClick={() => removeSetting(setting.id)}>
                    Odebrat
                  </button>
                </li>
              ))}
            </ul>
            <div className="v3-row">
              <input
                aria-label="Klíč nového nastavení"
                placeholder="klíč"
                value={newSettingKey}
                disabled={readOnly || busy}
                onChange={(e) => setNewSettingKey(e.target.value)}
              />
              <input
                aria-label="Hodnota nového nastavení"
                placeholder="hodnota"
                value={newSettingValue}
                disabled={readOnly || busy}
                onChange={(e) => setNewSettingValue(e.target.value)}
              />
              <button type="button" disabled={readOnly || busy || !newSettingKey.trim()} onClick={addSetting}>
                Přidat nastavení
              </button>
            </div>
          </section>

          <section className="v3-section" aria-label="Pravidla pro agenty">
            <h3>Pravidla {state.rules.length}</h3>
            {state.rules.length === 0 && <p className="v3-empty">Zatím žádná pravidla.</p>}
            <ul className="v3-rule-list">
              {state.rules.map((rule) => (
                <li key={rule.id} className={`v3-rule v3-rule-${rule.kind}`}>
                  <span className="v3-rule-text">{rule.text}</span>
                  <span className="v3-chip">{scopeLabel(rule)}</span>
                  <span className="v3-chip">{rule.kind === "must_not" ? "zákaz" : "pravidlo"}</span>
                  <button type="button" disabled={readOnly || busy} onClick={() => removeRule(rule.id)}>
                    Odebrat
                  </button>
                </li>
              ))}
            </ul>
            <div className="v3-row">
              <input
                aria-label="Nové pravidlo"
                placeholder="např. NE: číst .env"
                value={newRuleText}
                disabled={readOnly || busy}
                onChange={(e) => setNewRuleText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") addRule();
                }}
              />
              <select
                aria-label="Rozsah pravidla"
                value={newRuleScope}
                disabled={readOnly || busy}
                onChange={(e) => setNewRuleScope(e.target.value as RuleScope)}
              >
                <option value="project">Projekt</option>
                <option value="path" disabled={!path}>
                  Cesta {path || "(vyberte cestu)"}
                </option>
              </select>
              <button type="button" disabled={readOnly || busy || !newRuleText.trim()} onClick={addRule}>
                Přidat pravidlo
              </button>
            </div>
          </section>

          <section className="v3-section" aria-label="Rozhodnutí">
            <h3>Rozhodnutí · {pinnedCount} připnuto</h3>
            {sortedDecisions.length === 0 && <p className="v3-empty">Zatím žádná rozhodnutí.</p>}
            <ul className="v3-decision-list">
              {sortedDecisions.map((decision) => (
                <li key={decision.id} className={`v3-decision${decision.pinned ? " v3-pinned" : ""}`}>
                  <span className="v3-decision-date">{decision.createdAt}</span>
                  <span className="v3-decision-text">{decision.text}</span>
                  {decision.path && <span className="v3-chip">{decision.path}</span>}
                  <span className="v3-chip">{decision.by === "agent" ? "agent" : "člověk"}</span>
                  <button type="button" disabled={readOnly || busy} onClick={() => togglePin(decision.id)}>
                    {decision.pinned ? "Odepnout" : "Připnout"}
                  </button>
                </li>
              ))}
            </ul>
            <div className="v3-row">
              <input
                aria-label="Nové rozhodnutí"
                placeholder={`Rozhodnuto: … ${path ? `(naváže se na ${path})` : ""}`}
                value={newDecisionText}
                disabled={readOnly || busy}
                onChange={(e) => setNewDecisionText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") addDecision();
                }}
              />
              <button type="button" disabled={readOnly || busy || !newDecisionText.trim()} onClick={addDecision}>
                Zapsat rozhodnutí
              </button>
            </div>
          </section>
        </>
      )}
    </section>
  );
}
