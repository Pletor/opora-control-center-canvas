// Hlavní vlákno ke Workeru kódu animace: načtení modulu a fronta snímků. Fronta je sekvenční (worker kreslí jeden snímek
// naráz) a bere nejnovější požadavek první, takže při přehrávání nebo tažení vítězí poslední stav a staré snímky se zahodí.
import { describeError, type AssetBitmaps, type PaintRequest, type WorkerReply, type WorkerRequest } from "./code-module";

export type WorkerLike = {
  postMessage(message: WorkerRequest, transfer?: Transferable[]): void;
  terminate(): void;
  onmessage: ((event: { data: WorkerReply }) => void) | null;
  onerror: ((event: { message?: string }) => void) | null;
};
type Job = { id: number; request: PaintRequest; resolve: (bitmap: ImageBitmap | null) => void; reject: (error: Error) => void };

export const MAX_QUEUE = 80;
export const createCodeWorker = (): WorkerLike =>
  new Worker(new URL("./code-animation.worker.ts", import.meta.url), { type: "module" }) as unknown as WorkerLike;

export class CodeAnimationHost {
  /** Zavolá se, když kreslení přesáhne limit; parametr je naměřený čas v ms. */
  onSlow: ((ms: number) => void) | null = null;
  private worker: WorkerLike | null;
  private seq = 0;
  private loading: Promise<void> = Promise.resolve();
  private loadWaiter: { id: number; resolve: () => void; reject: (error: Error) => void } | null = null;
  private queue: Job[] = [];
  private current: Job | null = null;

  constructor(create: () => WorkerLike = createCodeWorker) {
    this.worker = create();
    this.worker.onmessage = (event) => this.reply(event.data);
    this.worker.onerror = (event) => this.crash(new Error(event.message || "Worker kódu animace selhal."));
  }

  /** Nahraje modul; paint požadavky čekají, až se dokončí. Odmítne se zprávou chyby modulu. */
  load(source: string): Promise<void> {
    const id = ++this.seq;
    this.loadWaiter?.reject(new Error("Kód byl mezitím vyměněn."));
    const pending = new Promise<void>((resolve, reject) => { this.loadWaiter = { id, resolve, reject }; });
    this.loading = pending;
    this.worker?.postMessage({ type: "load", id, source });
    return pending;
  }

  /** Předá workeru obrázky podkladů (vlastnictví bitmap přechází na worker); další snímky už je mají. */
  setAssets(images: AssetBitmaps): void {
    this.worker?.postMessage({ type: "assets", id: ++this.seq, images }, images.map((item) => item.bitmap));
  }

  /** Snímek pro požadavek; `null` znamená, že ho předběhl novější požadavek nebo host zanikl. */
  paint(request: PaintRequest): Promise<ImageBitmap | null> {
    return new Promise((resolve, reject) => {
      this.queue.push({ id: ++this.seq, request, resolve, reject });
      while (this.queue.length > MAX_QUEUE) this.queue.shift()?.resolve(null);
      void this.loading.then(() => this.pump(), (error: Error) => this.rejectAll(error));
    });
  }

  dispose() {
    this.worker?.terminate();
    this.worker = null;
    this.loadWaiter?.reject(new Error("Host zanikl."));
    this.loadWaiter = null;
    this.current?.resolve(null);
    this.current = null;
    for (const job of this.queue) job.resolve(null);
    this.queue = [];
  }

  private pump() {
    if (!this.worker || this.current) return;
    const job = this.queue.pop();
    if (!job) return;
    this.current = job;
    this.worker.postMessage({ type: "paint", id: job.id, ...job.request });
  }

  private reply(data: WorkerReply) {
    if (data.type === "loaded" || (data.type === "error" && data.id === this.loadWaiter?.id)) {
      const waiter = this.loadWaiter;
      if (!waiter || waiter.id !== data.id) return;
      this.loadWaiter = null;
      if (data.type === "loaded") waiter.resolve(); else waiter.reject(new Error(data.message));
      return;
    }
    if (data.type === "slow") { this.onSlow?.(data.ms); return; }
    const job = this.current;
    if (!job || job.id !== data.id) return;
    this.current = null;
    if (data.type === "frame") job.resolve(data.bitmap); else job.reject(new Error(data.message));
    this.pump();
  }

  private crash(error: Error) {
    this.loadWaiter?.reject(error);
    this.loadWaiter = null;
    this.current?.reject(error);
    this.current = null;
    this.rejectAll(error);
  }

  private rejectAll(error: Error) {
    for (const job of this.queue.splice(0)) job.reject(new Error(describeError(error)));
  }
}
