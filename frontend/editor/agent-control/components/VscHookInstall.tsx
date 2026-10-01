import { useEffect, useRef, useState } from "react";
import {
  fetchVscodeInstall,
  updateVscodeInstall,
  type VscodeInstallState,
} from "@/editor/agent-control/logic/agent-control-api";
import type { HookBinding } from "@/editor/agent-control/logic/hooks-control";

type Props = {
  binding: HookBinding;
  disabled: boolean;
  onChanged: () => Promise<void>;
};

/** Explicit per-session VS Code settings.local.json installer. It never launches a command. */
export default function VscHookInstall({ binding, disabled, onChanged }: Props) {
  const generation = useRef(0);
  const [state, setState] = useState<VscodeInstallState | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function readback(expectedBindingId = binding.id) {
    const request = ++generation.current;
    setError("");
    try {
      const value = await fetchVscodeInstall(expectedBindingId);
      if (request === generation.current && value.bindingId === binding.id) setState(value);
    } catch (reason) {
      if (request === generation.current) setError(reason instanceof Error ? reason.message : String(reason));
    }
  }

  useEffect(() => {
    generation.current++;
    setState(null);
    setError("");
    setBusy(false);
    void readback(binding.id);
  }, [binding.id, binding.revision]);

  async function change(action: "install" | "remove") {
    if (busy || disabled || !state || state.bindingId !== binding.id) return;
    const verb = action === "install" ? "nainstalovat" : "odebrat";
    if (!window.confirm(`Opravdu ${verb} Hook pouze pro session ${binding.sessionId} ve VS Code?`)) return;

    const request = ++generation.current;
    setBusy(true);
    setError("");
    try {
      await updateVscodeInstall(binding.id, binding.revision, state.settingsDigest, action);
      const readbackState = await fetchVscodeInstall(binding.id);
      if (request !== generation.current || readbackState.bindingId !== binding.id) return;
      setState(readbackState);
      await onChanged();
    } catch (reason) {
      if (request === generation.current) setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      if (request === generation.current) setBusy(false);
    }
  }

  const canInstall = !disabled && !busy && !!state?.canInstall && binding.state !== "stopped";
  const canRemove = !disabled && !busy && !!state?.installed;
  return <section className="agent-control__vscode" aria-label="VS Code Hook instalace">
    <h3 className="agent-control__heading">VS Code · vybraná session</h3>
    <p className="agent-control__meta">Binding revize: {binding.revision} · session: {binding.sessionId}</p>
    {state && <>
      <p className="agent-control__meta">{state.detail}</p>
      <p className="agent-control__meta">settings.local.json: {state.settingsPath}</p>
      <p className="agent-control__meta">SHA: {state.settingsDigest ?? "žádný settings soubor"}</p>
      {state.installed && !binding.hookObserved && <p className="agent-control__warning">Nainstalovaný JSON není důkaz běžícího hooku; čeká se na skutečnou doručenou událost.</p>}
    </>}
    <div className="agent-control__actions">
      <button type="button" className="agent-control__button" disabled={busy} onClick={() => void readback()}>Načíst SHA</button>
      <button type="button" className="agent-control__button agent-control__button--primary" disabled={!canInstall} onClick={() => void change("install")}>{busy ? "Zapisuji…" : "Nainstalovat"}</button>
      <button type="button" className="agent-control__button agent-control__button--danger" disabled={!canRemove} onClick={() => void change("remove")}>Odebrat</button>
    </div>
    {error && <p className="agent-control__error" role="alert">{error}</p>}
  </section>;
}
