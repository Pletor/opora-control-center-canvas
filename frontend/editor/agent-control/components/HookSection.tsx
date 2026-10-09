import { useEffect, useRef, useState } from "react";
import HookBindingForm from "@/editor/agent-control/components/HookBindingForm";
import HookBindingList from "@/editor/agent-control/components/HookBindingList";
import VscHookInstall from "@/editor/agent-control/components/VscHookInstall";
import {
  bindHook,
  controlHook,
  fetchBindings,
  fetchEvents,
  type BindInput,
  type HookBindingsResponse,
} from "@/editor/agent-control/logic/agent-control-api";
import { currentScope, isFreshScope, scopeKey, type Scope } from "@/editor/agent-control/logic/code-query";
import { canControlBinding, isBindingInScope, type HookBinding, type HookEvent } from "@/editor/agent-control/logic/hooks-control";

type Props = { active: boolean; project: string; workspace: string; selectedNodeId: string | null; readOnly: boolean };
type Generated = { scope: Scope; settingsPath: string; launchCommand: string };

/**
 * Hook control vybrané karty: připojení, události, Pause/Resume/Stop a instalace do VS Code.
 * Bind, control a instalaci smí jen člověk (server agentovi vrací 403). Data připojení se zahodí
 * dřív, než se nová karta stane ovladatelnou.
 */
export default function HookSection({ active, project, workspace, selectedNodeId, readOnly }: Props) {
  const scope = currentScope(project, workspace, selectedNodeId);
  const scopeRef = useRef<Scope>(scope);
  const bindingsRef = useRef<HookBinding[]>([]);
  const expandedRef = useRef<string | null>(null);
  const policyRef = useRef({ scopeReadOnly: true, ready: false });
  const ticket = useRef(0);
  const eventsTicket = useRef(0);
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
  const fail = (reason: unknown) => reason instanceof Error ? reason.message : String(reason);

  async function load(expected = scope): Promise<HookBindingsResponse | null> {
    if (!expected.nodeId) return null;
    const request = ++ticket.current;
    if (isFreshScope(expected, scopeRef.current)) { setLoading(true); setLoadError(""); }
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
        setLoadError(fail(reason));
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
      if (request === eventsTicket.current && isFreshScope(expected, scopeRef.current)) setError(fail(reason));
    }
  }

  useEffect(() => {
    ticket.current++;
    eventsTicket.current++;
    setBindings([]);
    setLoadedScope(null);
    setServerReadOnly(false);
    setLoading(false);
    setLoadError("");
    setExpandedId(null);
    setEvents([]);
    setEventsTruncated(false);
    setGenerated(null);
    setError("");
    if (active && scope.nodeId) void load(scope);
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
      if (isFreshScope(expected, scopeRef.current)) setError(fail(reason));
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
      if (isFreshScope(expected, scopeRef.current)) setError(fail(reason));
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
    const binding = value?.bindings.find((item) => item.id === expandedRef.current);
    if (binding && isFreshScope(expected, scopeRef.current)) await loadEvents(binding, expected);
  }

  async function copy(text: string) {
    try { await navigator.clipboard.writeText(text); }
    catch { setError("Kopírování odmítl prohlížeč."); }
  }

  if (!selectedNodeId) return <section className="agent-control__hook" aria-label="Hook control"><p className="agent-control__note">Vyberte kartu; Hook se váže na konkrétní uzel.</p></section>;
  const visibleGenerated = generated && isFreshScope(generated.scope, scope) ? generated : null;
  return <section className="agent-control__hook" aria-label="Hook control">
    <p className="agent-control__note">Hook pouze připravuje nastavení pro externí Claude. Aplikace nic nespouští. Připojení, ovládání a instalaci smí jen člověk.</p>
    {scopeReadOnly && <p className="agent-control__warning">Tento scope je pouze pro čtení; nové připojení, Resume a instalace jsou vypnuté. Ověřený existující hook lze stále Pause nebo Stop požádat při příští události.</p>}
    <div className="agent-control__refresh"><button type="button" className="agent-control__button" disabled={loading || !active} onClick={() => void refreshActivity()}>{loading ? "Obnovuji…" : "Obnovit aktivitu hooku"}</button><span className="agent-control__meta">Bez automatického polling; GET jen na vyžádání.</span></div>
    {loadError && <p className="agent-control__error" role="alert">{loadError}</p>}
    {error && <p className="agent-control__error" role="alert">{error}</p>}
    {!scopeLoaded && active && <p className="agent-control__note">Načítám stav tohoto scope…</p>}
    <HookBindingForm key={scopeKey("form", scope)} disabled={mutationDisabled} project={project} workspace={workspace} nodeId={selectedNodeId} onBind={onBind} />
    {visibleGenerated && <section className="agent-control__generated"><h3 className="agent-control__heading">Vygenerované nastavení</h3><code>{visibleGenerated.settingsPath}</code><button type="button" className="agent-control__button" onClick={() => void copy(visibleGenerated.settingsPath)}>Kopírovat cestu</button><code>{visibleGenerated.launchCommand}</code><button type="button" className="agent-control__button" onClick={() => void copy(visibleGenerated.launchCommand)}>Kopírovat launch command</button><p className="agent-control__warning">Příkaz se zde nikdy automaticky nespouští.</p></section>}
    <HookBindingList bindings={scopedBindings} readOnly={scopeReadOnly} disabled={!bindingsReady} expandedId={expandedId} events={events} eventsTruncated={eventsTruncated} onExpanded={(id) => void onExpanded(id)} onControl={onControl} />
    {expandedBinding && <VscHookInstall key={`${expandedBinding.id}:${expandedBinding.revision}`} binding={expandedBinding} disabled={mutationDisabled} onChanged={refreshActivity} />}
  </section>;
}
