// Worker kódu animace: načte modul uživatele přes Blob URL, kreslí do OffscreenCanvas a posílá hotové snímky jako ImageBitmap.
// Před importem zahodí fetch, XMLHttpRequest, importScripts a WebSocket; DOM tu není. Každé paint se měří (nad 50 ms zpráva slow).
import { BLOCKED_GLOBALS, SLOW_PAINT_MS, buildModuleSource, checkExports, describeError, forbiddenImport, type AnimationModule, type WorkerReply, type WorkerRequest } from "./code-module";

type Scope = { postMessage(message: WorkerReply, transfer?: Transferable[]): void; onmessage: ((event: MessageEvent<WorkerRequest>) => void) | null };
const scope = self as unknown as Scope & Record<string, unknown>;
let mod: AnimationModule | null = null;
let canvas: OffscreenCanvas | null = null;
/** Obrázky podkladů od hosta (`assets[].id` → ImageBitmap); kód animace je dostane jako 8. parametr paint, sám nic nenačítá. */
let images: Record<string, ImageBitmap> = {};

function blockGlobals() {
  for (const name of BLOCKED_GLOBALS) {
    try { scope[name] = undefined; } catch { /* vlastnost jen pro čtení: zkusí se níž */ }
    if (scope[name] !== undefined) { try { Object.defineProperty(self, name, { value: undefined, configurable: true }); } catch { /* zůstane, co je */ } }
  }
}

/** Pořadí načtení: opožděný starší import (top-level await v kódu) nesmí přepsat novější modul ani hlásit „loaded“. */
let generation = 0;

async function load(id: number, source: string) {
  blockGlobals();
  const mine = ++generation;
  const forbidden = forbiddenImport(source);
  if (forbidden) throw new Error(forbidden);
  const url = URL.createObjectURL(new Blob([buildModuleSource(source)], { type: "text/javascript" }));
  try {
    const loaded = (await import(/* @vite-ignore */ url)) as Record<string, unknown>;
    if (mine !== generation) return; // mezitím přišel novější kód; tento se zahodí beze zprávy (host už čeká na nový)
    const problem = checkExports(loaded);
    if (problem) throw new Error(problem);
    mod = loaded as unknown as AnimationModule;
    scope.postMessage({ type: "loaded", id });
  } finally { URL.revokeObjectURL(url); }
}

function paint(request: Extract<WorkerRequest, { type: "paint" }>) {
  if (!mod) throw new Error("Kód animace není načtený.");
  const { id, state, t, board, visible, width, height } = request;
  if (!canvas || canvas.width !== width || canvas.height !== height) canvas = new OffscreenCanvas(width, height);
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Plátno 2D není k dispozici.");
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.globalAlpha = 1;
  ctx.clearRect(0, 0, width, height);
  const started = performance.now();
  try { mod.paint(ctx, width, height, state, t, board, new Set(visible), Object.freeze({ ...images })); }
  catch (error) { throw new Error("paint selhal: " + describeError(error)); }
  const ms = performance.now() - started;
  if (ms > SLOW_PAINT_MS) scope.postMessage({ type: "slow", id, ms });
  const bitmap = canvas.transferToImageBitmap();
  scope.postMessage({ type: "frame", id, bitmap }, [bitmap]);
}

scope.onmessage = (event) => {
  const request = event.data;
  const fail = (error: unknown) => scope.postMessage({ type: "error", id: request.id, message: describeError(error) });
  if (request.type === "load") load(request.id, request.source).catch(fail);
  else if (request.type === "assets") {
    for (const old of Object.values(images)) old.close();
    images = Object.fromEntries(request.images.map((item) => [item.id, item.bitmap]));
    scope.postMessage({ type: "loaded", id: request.id });
  } else { try { paint(request); } catch (error) { fail(error); } }
};
