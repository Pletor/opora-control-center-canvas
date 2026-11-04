// Relace přehrávání případu: zavolá simulaci na serveru (jediný zdroj výpočtu), drží trasu, aktuální krok, běh a rychlost
// a pamatuje si výsledek porovnání s `expect` pro značky případů. Plátno jen čte; zápis do grafu tady nevzniká.
import { useEffect, useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { caseFingerprint, type CaseResult } from "../../flow-cases/logic/flow-cases";
import type { FlowCase, FlowGraph } from "../../logic/flow-types";
import { nextIndex, simulateError, stepEdge, stepMs, type SimulateResponse, type Speed, type TraceStep } from "./play-trace";

export const SIMULATE_URL = "/api/flow/simulate";
export const simulateCase = (graph: FlowGraph, flowCase: FlowCase) => api<SimulateResponse>(SIMULATE_URL, { graph, case: flowCase });

export type PlayState = {
  /** Běží relace (trasa je načtená); plátno je jen ke čtení, dokud se neukončí. */
  active: boolean; loading: boolean; error: string; playing: boolean; speed: Speed;
  response: SimulateResponse | null; index: number; step: TraceStep | null; edgeId: string | null;
  /** Mění se s každým krokem a restartem, aby se bod rozletěl znovu i na stejné hraně. */
  stamp: number; results: Readonly<Record<string, CaseResult>>;
  run: (flowCase: FlowCase) => void; play: () => void; pause: () => void; forward: () => void; back: () => void; restart: () => void; stop: () => void; setSpeed: (speed: Speed) => void;
};

export function usePlay(graph: FlowGraph): PlayState {
  const [response, setResponse] = useState<SimulateResponse | null>(null);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<Speed>(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [stamp, setStamp] = useState(0);
  const [results, setResults] = useState<Record<string, CaseResult>>({});
  const request = useRef(0);
  const trace = response?.trace ?? [];

  const go = (next: number) => { setIndex(next); setStamp((old) => old + 1); };
  const run = (flowCase: FlowCase) => {
    const mine = ++request.current;
    setLoading(true); setError(""); setPlaying(false);
    simulateCase(graph, flowCase).then((done) => {
      if (mine !== request.current) return;
      setResults((old) => ({ ...old, [flowCase.id]: { fingerprint: caseFingerprint(graph, flowCase), ok: done.expect ? done.expect.ok : null } }));
      setResponse(done); go(0); setPlaying(done.trace.length > 1);
    }, (failure) => { if (mine === request.current) { setResponse(null); setError(simulateError(failure)); } })
      .finally(() => { if (mine === request.current) setLoading(false); });
  };
  const stop = () => { request.current++; setResponse(null); setPlaying(false); setLoading(false); setError(""); };
  const step = (direction: 1 | -1) => { setPlaying(false); const next = nextIndex(index, trace.length, direction); if (next !== null) go(next); };

  useEffect(() => {
    if (!playing || !response) return;
    const timer = setTimeout(() => {
      const next = nextIndex(index, response.trace.length, 1);
      if (next === null) setPlaying(false); else go(next);
    }, stepMs(speed));
    return () => clearTimeout(timer);
  }, [playing, index, speed, response]);

  return {
    active: !!response || loading, loading, error, playing, speed, response, index, step: trace[index] ?? null, edgeId: stepEdge(graph, trace, index), stamp, results,
    run, stop, setSpeed, pause: () => setPlaying(false), forward: () => step(1), back: () => step(-1),
    // Po posledním kroku „Play“ začne od začátku, jinak pokračuje.
    play: () => { if (index >= trace.length - 1) go(0); setPlaying(trace.length > 1); },
    restart: () => { go(0); setPlaying(trace.length > 1); },
  };
}
