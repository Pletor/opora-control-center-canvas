import { useLayoutEffect, useRef, useState } from "react";
import { useDesktopState } from "@/shared/desktop-state/logic/state-store";
import type { Rule, RuleScope, Decision, Setting } from "@/shared/desktop-state/logic/types";
import MemoryItemText from "./MemoryItemText";
import RuleReview from "./RuleReview";
import { asHumanRule, isAgentRule, type RuleReviewDecision } from "@/shared/desktop-state/logic/agent-rule";
import { fromRoundLabel } from "@/editor/node-detail/rounds/logic/rounds-model";
import { useDecisionRounds } from "@/editor/node-detail/rounds/logic/use-decision-rounds";

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
  const { state, readOnly, loading, error, reload, mutate, mutateItem, reviewRule } = useDesktopState(project, workspace);
  const [newSettingKey, setNewSettingKey] = useState("");
  const [newSettingValue, setNewSettingValue] = useState("");
  const [newRuleText, setNewRuleText] = useState("");
  const [newRuleScope, setNewRuleScope] = useState<RuleScope>("project");
  const [newDecisionText, setNewDecisionText] = useState("");
  const [busy, setBusy] = useState(false);
  // Rozhodnutí karty z dřívějšího kola nesou štítek „z v1“ (kolo vzniku podle zamrazené historie kol).
  const decisionRound = useDecisionRounds(project, workspace, state.decisions, state.nodes);

  // Verze konceptů: úspěšný zápis smaže koncept jen tehdy, když se od odeslání nezměnil (klíč a
  // hodnota nastavení tvoří jednu dvojici s jednou verzí), takže nikdy nesmaže novější text.
  const settingDraftVersion = useRef(0);
  const ruleDraftVersion = useRef(0);
  const decisionDraftVersion = useRef(0);

  // Jeden synchronní zámek pro celý whole-state dokument (viz NodeWorkflowPanel): druhá mutace se
  // neodešle, dokud předchozí není usazená. Uvolnění až v layout efektu po commitu, aby další
  // obsluha pracovala s čerstvým stavem a revizí.
  const saveLockRef = useRef(false);
  const [settledCount, setSettledCount] = useState(0);
  useLayoutEffect(() => {
    saveLockRef.current = false;
  }, [settledCount]);

  const run = (fn: (current: typeof state) => typeof state) => runAction(() => mutate(fn));
  const itemWrite = (kind: "rule" | "decision", before: Rule | Decision | null, after: Rule | Decision | null) =>
    runAction(() => mutateItem(kind, before, after));

  async function runAction(action: () => Promise<boolean>): Promise<boolean> {
    if (saveLockRef.current) return false;
    saveLockRef.current = true;
    setBusy(true);
    try {
      return await action();
    } finally {
      setBusy(false);
      setSettledCount((n) => n + 1);
    }
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
    const key = newSettingKey.trim();
    if (!key) return;
    const value = newSettingValue.trim();
    const setting: Setting = { id: newId(), key, value };
    const submittedVersion = settingDraftVersion.current;
    run((current) => ({ ...current, settings: current.settings.concat([setting]) })).then((ok) => {
      if (ok && settingDraftVersion.current === submittedVersion) {
        setNewSettingKey("");
        setNewSettingValue("");
      }
    });
  }

  function addRule() {
    const raw = newRuleText.trim();
    if (!raw) return;
    const negative = /^ne\s*:/i.test(raw);
    const text = negative ? raw.replace(/^ne\s*:\s*/i, "") : raw;
    const target = newRuleScope === "path" ? path : "";
    if (newRuleScope === "path" && !path) return;
    const rule: Rule = { id: newId(), text, kind: negative ? "must_not" : "must", scope: newRuleScope, target };
    const submittedVersion = ruleDraftVersion.current;
    itemWrite("rule", null, rule).then((ok) => {
      if (ok && ruleDraftVersion.current === submittedVersion) setNewRuleText("");
    });
  }

  // Schválení i zamítnutí návrhu agenta jde přes /rule-review (smí jen člověk, CAS na přečtený návrh).
  function review(rule: Rule, decision: RuleReviewDecision) {
    return runAction(() => reviewRule(rule, decision));
  }

  function removeRule(id: string) {
    const rule = state.rules.find((r) => r.id === id);
    return rule ? itemWrite("rule", rule, null) : Promise.resolve(false);
  }

  function addDecision() {
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
    const submittedVersion = decisionDraftVersion.current;
    itemWrite("decision", null, decision).then((ok) => {
      if (ok && decisionDraftVersion.current === submittedVersion) setNewDecisionText("");
    });
  }

  function togglePin(id: string) {
    const decision = state.decisions.find((d) => d.id === id);
    return decision ? itemWrite("decision", decision, { ...decision, pinned: !decision.pinned }) : Promise.resolve(false);
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
            <h3>Fakta projektu</h3>
            <p>Společné hodnoty projektu. Karty na ně odkazují přes stabilní ID; změna hodnoty se projeví u všech odkazů.</p>
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
                onChange={(e) => {
                  settingDraftVersion.current += 1;
                  setNewSettingKey(e.target.value);
                }}
              />
              <input
                aria-label="Hodnota nového nastavení"
                placeholder="hodnota"
                value={newSettingValue}
                disabled={readOnly || busy}
                onChange={(e) => {
                  settingDraftVersion.current += 1;
                  setNewSettingValue(e.target.value);
                }}
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
                <li key={rule.id} className={`v3-rule v3-rule-${rule.kind}`}
                  style={isAgentRule(rule) ? { opacity: 0.6, fontStyle: "italic" } : undefined}>
                  {/* Úprava textu člověkem pravidlo zároveň schválí (stejně jako na kartě). */}
                  <MemoryItemText id={`rule:${rule.id}`} text={rule.text} disabled={readOnly || busy}
                    save={(text) => itemWrite("rule", rule, asHumanRule(rule, text))} />
                  <span className="v3-chip">{scopeLabel(rule)}</span>
                  <span className="v3-chip">{rule.kind === "must_not" ? "zákaz" : "pravidlo"}</span>
                  <RuleReview rule={rule} disabled={readOnly || busy} review={(item, decision) => void review(item, decision)} />
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
                onChange={(e) => {
                  ruleDraftVersion.current += 1;
                  setNewRuleText(e.target.value);
                }}
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
                  {state.decisions.some(d => d.supersedes === decision.id) ? <del>{decision.text}</del> :
                    <MemoryItemText id={`decision:${decision.id}`} text={decision.text} disabled={readOnly || busy} actionLabel="Opravit rozhodnutí"
                      save={(text) => itemWrite("decision", null, { ...decision, id: newId(), text, supersedes: decision.id, by: "human", createdAt: new Date().toISOString() })} />}
                  {decision.supersedes && <span className="v3-chip">Oprava rozhodnutí {decision.supersedes}</span>}
                  <button type="button" disabled={readOnly || busy || !!decision.supersedes || state.decisions.some(d => d.supersedes === decision.id)} onClick={() => itemWrite("decision", decision, null)}>Odebrat</button>
                  {decision.path && <span className="v3-chip">{decision.path}</span>}
                  <span className="v3-chip">{decision.by === "agent" ? "agent" : "člověk"}</span>
                  {decisionRound.has(decision.id) && (
                    <span className="v3-chip" data-testid="decision-from-round"
                      title={`Rozhodnutí vzniklo v kole v${decisionRound.get(decision.id)} karty; aktuální kolo ho nepřebírá jako volbu, jen jako kontext.`}>
                      {fromRoundLabel(decisionRound.get(decision.id))}
                    </span>
                  )}
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
                onChange={(e) => {
                  decisionDraftVersion.current += 1;
                  setNewDecisionText(e.target.value);
                }}
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
