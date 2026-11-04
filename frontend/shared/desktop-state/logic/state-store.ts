// Sdílená logika načtení/uložení State s CAS ochranou (expectedRevision) a ochranou
// proti zastaralým async odpovědím (scoped A->B->A). Interní modul, nikoli veřejný export.
import { useEffect, useRef, useState } from "react";
import { trackSaveWrite } from "@/shared/hooks/logic/save-coordinator";
import { errorMessage, fetchState, saveNode, saveState } from "@/shared/desktop-state/logic/api";
import type { DesktopState } from "@/shared/desktop-state/logic/types";
import { emptyDesktopState } from "@/shared/desktop-state/logic/types";
import type { Rule, Decision, StateResponse } from "@/shared/desktop-state/logic/types";
import { appliesTo, stateChange, withItem, withNode, type ItemWriteResponse, type ItemWriteSlim } from "@/shared/desktop-state/logic/slim-writes";
import { api } from "@/shared/types/logic/types";
import { ruleReviewRequest, type RuleReviewDecision } from "@/shared/desktop-state/logic/agent-rule";

export type DesktopStateHandle = {
  mutateItem: (kind: "rule" | "decision", expected: Rule | Decision | null, item: Rule | Decision | null) => Promise<boolean>;
  /** Člověk schválí nebo zamítne návrh pravidla od agenta (POST /api/desktop-v3/rule-review, agent dostane 403). */
  reviewRule: (rule: Rule, decision: RuleReviewDecision) => Promise<boolean>;
  state: DesktopState;
  revision: number;
  readOnly: boolean;
  loading: boolean;
  error: string;
  /**
   * Znovu načte stav ze serveru (např. po zápisu jiného procesu přes backend).
   * Když právě běží uložení, počká na jeho konec: rozpracovaná změna se nepřepíše ani nezahodí.
   */
  reload: () => void;
  /**
   * Aplikuje mutaci na aktuální stav a uloží ji s CAS ochranou. Změna jediné karty jde štíhle
   * (POST /api/desktop-v3/node, oprava 8), jiná změna celým stavem, mutace beze změny nikam.
   */
  mutate: (fn: (current: DesktopState) => DesktopState) => Promise<boolean>;
  /** Převezme stav z odpovědi adresného zápisu (autonomie, hromadné potvrzení) a pošle ho ostatním instancím. */
  apply: (value: StateResponse) => void;
  /**
   * Štíhlá odpověď zápisu (revize + změněná položka, karta P3): `patch` z ní udělá nový stav, ze
   * kterého zápis vyšel (`baseRevision`). Jiná revize nebo změna grafu = stav se načte celý.
   */
  applySlim: (baseRevision: number, response: { revision: number; readOnly: boolean; graphChanged?: boolean }, patch: (current: DesktopState) => DesktopState) => void;
};

type Published = { state: DesktopState; revision: number; readOnly: boolean };
type Listener = (value: Published) => void;
// Více instancí hooku nad stejným scope (panel uzlu, bloky na plátně) sdílí jednu revizi:
// po úspěšném čtení či zápisu jedné instance dostanou ostatní tentýž stav, jinak by další
// zápis narazil na CAS („revize nesouhlasí“) jen proto, že ho provedlo jiné okno téže stránky.
const listeners = new Map<string, Set<Listener>>();

function publish(scope: string, value: Published, except: Listener) {
  for (const listener of listeners.get(scope) ?? []) if (listener !== except) listener(value);
}

export function useDesktopState(project: string, workspace: string): DesktopStateHandle {
  const [state, setState] = useState<DesktopState>(emptyDesktopState());
  const [revision, setRevision] = useState(0);
  const [readOnly, setReadOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const generation = useRef(0);
  const scopeKey = useRef("");
  const listener = useRef<Listener>(() => {});
  listener.current = (value) => {
    setState(value.state);
    setRevision(value.revision);
    setReadOnly(value.readOnly);
  };
  const self = useRef<Listener>((value) => listener.current(value));
  const saving = useRef(0);
  const reloadQueued = useRef(false);
  // Poslední vykreslený stav a revize: štíhlá odpověď zápisu se vkládá do nich, ne do stavu z doby volání.
  const latest = useRef({ state, revision });
  latest.current = { state, revision };

  useEffect(() => {
    const scope = `${project}::${workspace}`;
    const set = listeners.get(scope) ?? new Set<Listener>();
    set.add(self.current);
    listeners.set(scope, set);
    return () => {
      set.delete(self.current);
      if (set.size === 0) listeners.delete(scope);
    };
  }, [project, workspace]);

  const load = () => {
    const ticket = ++generation.current;
    const scope = `${project}::${workspace}`;
    scopeKey.current = scope;
    setLoading(true);
    setError("");
    fetchState(project, workspace)
      .then((value) => {
        if (ticket !== generation.current || scopeKey.current !== scope) return;
        setState(value.state);
        setRevision(value.revision);
        setReadOnly(value.readOnly);
        setLoading(false);
        publish(scope, value, self.current);
      })
      .catch((e) => {
        if (ticket !== generation.current || scopeKey.current !== scope) return;
        setError(errorMessage(e));
        setLoading(false);
      });
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project, workspace]);

  const mutate = async (fn: (current: DesktopState) => DesktopState): Promise<boolean> => {
    if (readOnly) {
      setError("Main je pouze pro čtení; změny nelze uložit.");
      return false;
    }
    const ticket = generation.current;
    const scope = `${project}::${workspace}`;
    const previous = state;
    const previousRevision = revision;
    const next = fn(previous);
    const change = stateChange(previous, next);
    if (change.kind === "none") return true;
    // Apply immediately so controls (e.g. native checkboxes) reflect the user's action without
    // waiting on the round trip; reconciled with the server's exact saved state below, or rolled
    // back on failure/staleness.
    setState(next);
    saving.current++;
    try {
      if (change.kind === "node") {
        const slim = await trackSaveWrite(project, workspace, saveNode(project, workspace, previousRevision, change.nodeId, change.node));
        if (ticket !== generation.current || scopeKey.current !== scope) return false;
        settleSlim(scope, previousRevision, slim, (current) => withNode(current, slim.nodeId, slim.node));
        return true;
      }
      const value = await trackSaveWrite(project, workspace, saveState(project, workspace, previousRevision, next));
      if (ticket !== generation.current || scopeKey.current !== scope) return false;
      setState(value.state);
      setRevision(value.revision);
      setReadOnly(value.readOnly);
      setError("");
      publish(scope, value, self.current);
      if (value.graphChanged) window.dispatchEvent(new CustomEvent("opora:spawned", { detail: { project, workspace } }));
      return true;
    } catch (e) {
      if (ticket !== generation.current || scopeKey.current !== scope) return false;
      setState(previous);
      setError(errorMessage(e));
      return false;
    } finally {
      saving.current--;
      if (saving.current === 0 && reloadQueued.current) {
        reloadQueued.current = false;
        load();
      }
    }
  };

  const reload = () => {
    if (saving.current > 0) reloadQueued.current = true;
    else load();
  };

  // Štíhlá odpověď vlastního zápisu se vloží do posledního vykresleného stavu; jiná revize nebo změna
  // grafu = stav se načte celý, až doběhnou všechny rozepsané zápisy.
  const settleSlim = (scope: string, baseRevision: number, value: { revision: number; readOnly: boolean; graphChanged?: boolean }, patch: (current: DesktopState) => DesktopState) => {
    if (appliesTo(baseRevision, value) && latest.current.revision === baseRevision) {
      const next = patch(latest.current.state);
      setState(next); setRevision(value.revision); setReadOnly(value.readOnly); setError("");
      publish(scope, { state: next, revision: value.revision, readOnly: value.readOnly }, self.current);
    } else {
      reloadQueued.current = true;
    }
    if (value.graphChanged) window.dispatchEvent(new CustomEvent("opora:spawned", { detail: { project, workspace } }));
  };

  // Adresný zápis jedné položky (pravidlo, rozhodnutí, posouzení návrhu): odpověď nese jen revizi a
  // uloženou položku (karta P3), ne celý stav.
  const writeItem = (kind: "rule" | "decision", id: string, url: string, body: object) =>
    writeSlim<ItemWriteResponse>(url, body, (current, value) => withItem(current, kind, id, value.item));
  // Hromadné posouzení vrací totéž pro každou položku dávky; vloží se všechny jednou revizí.
  const writeSlim = async <R extends ItemWriteSlim>(url: string, body: object, patch: (current: DesktopState, value: R) => DesktopState) => {
    const ticket = generation.current;
    const scope = `${project}::${workspace}`;
    const baseRevision = revision;
    saving.current++;
    try {
      const value = await trackSaveWrite(project, workspace, api<R>(url, body));
      if (ticket !== generation.current || scopeKey.current !== scope) return false;
      settleSlim(scope, baseRevision, value, (current) => patch(current, value));
      return true;
    } catch (e) {
      if (ticket === generation.current && scopeKey.current === scope) setError(errorMessage(e));
      return false;
    } finally {
      saving.current--;
      if (saving.current === 0 && reloadQueued.current) { reloadQueued.current = false; load(); }
    }
  };
  const mutateItem: DesktopStateHandle["mutateItem"] = async (kind, expected, item) => {
    if (readOnly || (!expected && !item)) return false;
    const id = (item ?? expected)!.id;
    return writeItem(kind, id, `/api/desktop-v3/${kind}`, {
      project, workspace, id, expected, item,
      op: !expected ? "add" : !item ? "remove" : "update",
    });
  };
  const reviewRule: DesktopStateHandle["reviewRule"] = async (rule, decision) => {
    if (readOnly) return false;
    const request = ruleReviewRequest(project, workspace, rule, decision);
    return writeItem("rule", rule.id, request.url, request.body);
  };
  const apply = (value: StateResponse) => {
    const scope = `${project}::${workspace}`;
    generation.current++;
    setState(value.state); setRevision(value.revision); setReadOnly(value.readOnly); setError("");
    publish(scope, value, self.current);
  };
  const applySlim: DesktopStateHandle["applySlim"] = (baseRevision, response, patch) => {
    if (!appliesTo(baseRevision, response) || latest.current.revision !== baseRevision) {
      reload();
      return;
    }
    apply({ state: patch(latest.current.state), revision: response.revision, readOnly: response.readOnly });
  };
  return { state, revision, readOnly, loading, error, reload, mutate, mutateItem, reviewRule, apply, applySlim };
}
