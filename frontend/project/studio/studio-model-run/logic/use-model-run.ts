// Běh MODELu pro rodiče (StudioModelWorkspace): drží stav běhu, smyčku ticku a hlášku. Krok čte vždy aktuální model
// (i neuložený), takže nově naplánovaný incident platí od dalšího ticku. Změna toho, co engine počítá (typy,
// konfigurace, vazby; viz `runSignature`), běh zastaví a vynuluje a řekne to hláškou: čísla na plátně tak vždy patří
// k modelu, který je vidět, a nikdy nemíchají dva různé grafy. Poloha a název karty běh nechají.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ModelCommandKind } from "../../model/simulation/logic";
import type { EditModel } from "../../studio-model/logic/model-edit";
import { saveProblem } from "../../studio-model/logic/model-save";
import { advanceRun, clampSpeed, commandRun, initialRun, resetRun, runSignature, runTouched, tickDelayMs, type RunState } from "./run-control";

export function useModelRun(model: EditModel, onNotice: (text: string) => void) {
  const [run, setRun] = useState<RunState>(() => initialRun());
  const modelRef = useRef(model);
  modelRef.current = model;
  const runRef = useRef(run);
  runRef.current = run;
  const signature = useMemo(() => runSignature(model), [model]);
  const seen = useRef(signature);

  useEffect(() => {
    if (seen.current === signature) return;
    seen.current = signature;
    if (!runTouched(runRef.current)) return;
    setRun(resetRun);
    onNotice("Model se změnil: běh se zastavil a vynuloval, čísla patří k aktuálnímu modelu.");
  }, [signature, onNotice]);

  // Smyčka ticku jako v prototypu (`start`): další tick naplánuje až skončený předchozí, prodleva podle rychlosti.
  // Nejde o polling (pravidlo `poller.test.ts`): nic se nenačítá, jen se počítá další modelová sekunda.
  useEffect(() => {
    if (!run.running) return;
    let timer = 0;
    const tick = () => {
      setRun((current) => current.running ? advanceRun(modelRef.current, current) : current);
      timer = window.setTimeout(tick, tickDelayMs(run.speed));
    };
    timer = window.setTimeout(tick, tickDelayMs(run.speed));
    return () => window.clearTimeout(timer);
  }, [run.running, run.speed]);

  const ready = useCallback(() => {
    if (!modelRef.current.nodes.length) { onNotice("Model je prázdný: přidejte komponentu nebo otevřete scénář."); return false; }
    const problem = saveProblem(modelRef.current);
    if (problem) { onNotice(`Model nejde spustit: ${problem}`); return false; }
    return true;
  }, [onNotice]);

  const start = useCallback(() => {
    if (!ready()) return;
    setRun((current) => { const next = advanceRun(modelRef.current, current); return { ...next, running: !next.error }; });
  }, [ready]);
  const pause = useCallback(() => setRun((current) => ({ ...current, running: false })), []);
  const step = useCallback(() => { if (ready()) setRun((current) => advanceRun(modelRef.current, { ...current, running: false })); }, [ready]);
  const reset = useCallback(() => setRun(resetRun), []);
  const setSpeed = useCallback((speed: number) => setRun((current) => ({ ...current, speed: clampSpeed(speed) })), []);
  const command = useCallback((kind: ModelCommandKind, nodeIds: readonly string[] = []) => {
    if (!ready()) return;
    setRun((current) => commandRun(modelRef.current, current, kind, nodeIds));
  }, [ready]);

  return { run, start, pause, step, reset, setSpeed, command };
}
