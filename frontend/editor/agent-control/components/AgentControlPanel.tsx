import { useEffect, useRef, useState } from "react";
import HookBindingForm from "@/editor/agent-control/components/HookBindingForm";
import HookBindingList from "@/editor/agent-control/components/HookBindingList";
import LspControl from "@/editor/agent-control/components/LspControl";
import SemanticQuery from "@/editor/agent-control/components/SemanticQuery";
import VscHookInstall from "@/editor/agent-control/components/VscHookInstall";
import {
  bindHook,
  controlHook,
  fetchBindings,
  fetchEvents,
  fetchLspStatus,
  queryLsp,
  type BindInput,
  type HookBindingsResponse,
  type LspStatus,
} from "@/editor/agent-control/logic/agent-control-api";
import {
  canControlBinding,
  currentScope,
  isBindingInScope,
  isFreshScope,
  type HookBinding,
  type HookEvent,
  type Scope,
} from "@/editor/agent-control/logic/hooks-control";

type Props = { active: boolean; project: string; workspace: string; selectedNodeId: string | null; readOnly: boolean };
type Generated = { scope: Scope; settingsPath: string; launchCommand: string };

/** Binding data is deliberately invalidated before a new card scope becomes actionable. */
export default function AgentControlPanel({ active, project, workspace, selectedNodeId, readOnly }: Props) {
  const scope = currentScope(project, workspace, selectedNodeId);
  const scopeRef = useRef<Scope>(scope);
  const bindingsRef = useRef<HookBinding[]>([]);
  const expandedRef = useRef<string | null>(null);
  const policyRef = useRef({ scopeReadOnly: true, ready: false });
  const ticket = useRef(0);
  const eventsTicket = useRef(0);
  const lspTicket = useRef(0);
  scopeRef.current = scope;

  const [bindings, setBindings] = useState<HookBinding[]>([]);
  const [loadedScope, setLoadedScope] = useState<Scope | null>(null);
  const [serverReadOnly, setServerReadOnly] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [events, setEvents] = useState<HookEvent[]>([]);
  const [eventsTruncated, setEventsTruncated] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [generated, setGenerated] = useState<Generated | null>(null);
  const [lspStatus, setLspStatus] = useState<LspStatus | null>(null);
  const [error, setError] = useState("");

  const scopeLoaded = loadedScope !== null && isFreshScope(loadedScope, scope);
  const bindingsReady = active && scopeLoaded && !loading && !loadError;
  const scopeReadOnly = readOnly || (scopeLoaded && serverReadOnly);
  const mutationDisabled = scopeReadOnly || !bindingsReady;
  policyRef.current = { scopeReadOnly, ready: bindingsReady };
  bindingsRef.current = bindings;
  expandedRef.current = expandedId;
  const scopedBindings = scopeLoaded ? bindings.filter((binding) => isBindingInScope(binding, scope)) : [];
  const expandedBinding = scopedBindings.find((binding) => binding.id === expandedId) ?? null;

  async function load(expected = scope): Promise<HookBindingsResponse | null> {
    if (!expected.nodeId) return null;
    const request = ++ticket.current;
    if (isFreshScope(expected, scopeRef.current)) {
      setLoading(true);
      setLoadError("");
    }
    try {
      const value = await fetchBindings({ project: expected.project, workspace: expected.workspace, nodeId: expected.nodeId });
      if (request !== ticket.current || !isFreshScope(expected, scopeRef.current)) return null;
      const safeBindings = value.bindings.filter((binding) => isBindingInScope(binding, expected));
      setBindings(safeBindings);
      setServerReadOnly(value.readOnly);
      setLoadedScope(expected);
      return { ...value, bindings: safeBindings };
    } catch (reason) {
      if (request === ticket.current && isFreshScope(expected, scopeRef.current)) {
        // Never keep a previous card's controls actionable after a failed reload.
        setBindings([]);
        setServerReadOnly(false);
        setLoadedScope(expected);
        setLoadError(reason instanceof Error ? reason.message : String(reason));
      }
      return null;
    } finally {
      if (request === ticket.current && isFreshScope(expected, scopeRef.current)) setLoading(false);
    }
  }

  async function loadEvents(binding: HookBinding, expected: Scope) {
    if (!isBindingInScope(binding, expected)) return;
    const request = ++eventsTicket.current;
    try {
      const value = await fetchEvents(binding.id);
      if (request === eventsTicket.current && isFreshScope(expected, scopeRef.current) && isBindingInScope(binding, scopeRef.current)) {
        setEvents(value.events);
        setEventsTruncated(value.truncated);
      }
    } catch (reason) {
      if (request === eventsTicket.current && isFreshScope(expected, scopeRef.current)) setError(reason instanceof Error ? reason.message : String(reason));
    }
  }

  useEffect(() => {
    ticket.current++;
    eventsTicket.current++;
    lspTicket.current++;
    setBindings([]);
    setLoadedScope(null);
    setServerReadOnly(false);
    setLoading(false);
    setLoadError("");
    setExpandedId(null);
    setEvents([]);
    setEventsTruncated(false);
    setGenerated(null);
    setLspStatus(null);
    setError("");
    if (!active || !scope.nodeId) return;

    void load(scope);
    const request = ++lspTicket.current;
    fetchLspStatus({ project: scope.project, workspace: scope.workspace }).then((value) => {
      if (request === lspTicket.current && isFreshScope(scope, scopeRef.current)) setLspStatus(value);
    }).catch((reason) => {
      if (request === lspTicket.current && isFreshScope(scope, scopeRef.current)) setError(reason instanceof Error ? reason.message : String(reason));
    });
  }, [active, project, workspace, selectedNodeId]);

  async function onBind(input: BindInput) {
    const expected = scope;
    const inputScope = currentScope(input.project, input.workspace, input.nodeId);
    if (!isFreshScope(expected, scopeRef.current) || !isFreshScope(expected, inputScope) || !policyRef.current.ready || policyRef.current.scopeReadOnly) return;
    setError("");
    try {
      const result = await bindHook(input);
      if (!isFreshScope(expected, scopeRef.current)) return;
      setGenerated({ scope: expected, settingsPath: result.settingsPath, launchCommand: result.launchCommand });
      await load(expected);
    } catch (reason) {
      if (isFreshScope(expected, scopeRef.current)) setError(reason instanceof Error ? reason.message : String(reason));
    }
  }

  async function onControl(binding: HookBinding, action: "pause" | "resume" | "stop") {
    const expected = scope;
    if (!isFreshScope(expected, scopeRef.current) || !policyRef.current.ready ||
      !isBindingInScope(binding, expected) || !canControlBinding(policyRef.current.scopeReadOnly, binding, action)) return;
    setError("");
    try {
      await controlHook(binding.id, binding.revision, action);
      if (isFreshScope(expected, scopeRef.current)) await load(expected);
    } catch (reason) {
      if (isFreshScope(expected, scopeRef.current)) setError(reason instanceof Error ? reason.message : String(reason));
    }
  }

  async function onExpanded(bindingId: string | null) {
    const expected = scope;
    eventsTicket.current++;
    setExpandedId(bindingId);
    setEvents([]);
    setEventsTruncated(false);
    if (!bindingId) return;
    const binding = bindingsRef.current.find((item) => item.id === bindingId);
    if (!binding || !isFreshScope(expected, scopeRef.current) || !isBindingInScope(binding, expected)) return;
    await loadEvents(binding, expected);
  }

  async function refreshActivity() {
    const expected = scope;
    setError("");
    const value = await load(expected);
    const expanded = expandedRef.current;
    const binding = value?.bindings.find((item) => item.id === expanded);
    if (binding && isFreshScope(expected, scopeRef.current)) await loadEvents(binding, expected);
  }

  async function copy(text: string) {
    try { await navigator.clipboard.writeText(text); }
    catch { setError("Kopírování odmítl prohlížeč."); }
  }

  if (!selectedNodeId) return <div className="agent-control" data-testid="agent-control"><p className="agent-control__note">Vyberte kartu; Hook se váže na konkrétní uzel.</p></div>;
  const visibleGenerated = generated && isFreshScope(generated.scope, scope) ? generated : null;
  return <div className="agent-control" data-testid="agent-control">
    <p className="agent-control__note">Hook pouze připravuje nastavení pro externí Claude. Aplikace nic nespouští.</p>
    {scopeReadOnly && <p className="agent-control__warning">Tento scope je pouze pro čtení; nové připojení, Resume a instalace jsou vypnuté. Ověřený existující hook lze stále Pause nebo Stop požádat při příští události. LSP a sémantické čtení zůstávají dostupné.</p>}
    <div className="agent-control__refresh"><button type="button" className="agent-control__button" disabled={loading || !active} onClick={() => void refreshActivity()}>{loading ? "Obnovuji…" : "Obnovit aktivitu hooku"}</button><span className="agent-control__meta">Bez automatického polling; GET jen na vyžádání.</span></div>
    {loadError && <p className="agent-control__error" role="alert">{loadError}</p>}
    {error && <p className="agent-control__error" role="alert">{error}</p>}
    {!scopeLoaded && active && <p className="agent-control__note">Načítám stav tohoto scope…</p>}
    <HookBindingForm key={`${project}:${workspace}:${selectedNodeId}`} disabled={mutationDisabled} project={project} workspace={workspace} nodeId={selectedNodeId} onBind={onBind} />
    {visibleGenerated && <section className="agent-control__generated"><h3 className="agent-control__heading">Vygenerované nastavení</h3><code>{visibleGenerated.settingsPath}</code><button type="button" className="agent-control__button" onClick={() => void copy(visibleGenerated.settingsPath)}>Kopírovat cestu</button><code>{visibleGenerated.launchCommand}</code><button type="button" className="agent-control__button" onClick={() => void copy(visibleGenerated.launchCommand)}>Kopírovat launch command</button><p className="agent-control__warning">Příkaz se zde nikdy automaticky nespouští.</p></section>}
    <HookBindingList bindings={scopedBindings} readOnly={scopeReadOnly} disabled={!bindingsReady} expandedId={expandedId} events={events} eventsTruncated={eventsTruncated} onExpanded={(id) => void onExpanded(id)} onControl={onControl} />
    {expandedBinding && <VscHookInstall key={`${expandedBinding.id}:${expandedBinding.revision}`} binding={expandedBinding} disabled={mutationDisabled} onChanged={refreshActivity} />}
    <LspControl key={`${project}:${workspace}:${selectedNodeId}`} disabled={!active} project={project} workspace={workspace} nodeId={selectedNodeId} status={scopeLoaded ? lspStatus : null} onQuery={queryLsp} />
    <SemanticQuery key={`${project}:${workspace}:${selectedNodeId}`} disabled={!active} project={project} workspace={workspace} />
  </div>;
}
