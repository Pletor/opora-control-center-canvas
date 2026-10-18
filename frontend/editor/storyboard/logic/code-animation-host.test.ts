import { describe, expect, it } from "vitest";
import { CodeAnimationHost, MAX_QUEUE, type WorkerLike } from "./code-animation-host";
import type { PaintRequest, WorkerReply, WorkerRequest } from "./code-module";

function fakeWorker() {
  const sent: WorkerRequest[] = [];
  const worker: WorkerLike & { terminated: boolean; reply(data: WorkerReply): void } = {
    terminated: false, onmessage: null, onerror: null,
    postMessage(message) { sent.push(message); }, terminate() { this.terminated = true; },
    reply(data) { this.onmessage?.({ data }); },
  };
  return { worker, sent };
}
const req = (t: number): PaintRequest => ({ state: {}, t, board: {} as PaintRequest["board"], visible: [], width: 10, height: 10 });
const tick = () => new Promise((r) => setTimeout(r, 0));
const bitmap = (n: number) => ({ n }) as unknown as ImageBitmap;

describe("CodeAnimationHost", () => {
  it("snímky čekají na načtení modulu a nejnovější požadavek jde první", async () => {
    const { worker, sent } = fakeWorker();
    const host = new CodeAnimationHost(() => worker);
    const loaded = host.load("src");
    const first = host.paint(req(1)), last = host.paint(req(2));
    await tick();
    expect(sent.map((m) => m.type)).toEqual(["load"]);
    worker.reply({ type: "loaded", id: sent[0].id });
    await loaded; await tick();
    const paint = sent[1] as Extract<WorkerRequest, { type: "paint" }>;
    expect(paint.t).toBe(2);
    worker.reply({ type: "frame", id: paint.id, bitmap: bitmap(2) });
    expect(await last).toEqual(bitmap(2));
    await tick();
    expect((sent[2] as Extract<WorkerRequest, { type: "paint" }>).t).toBe(1);
    worker.reply({ type: "frame", id: sent[2].id, bitmap: bitmap(1) });
    expect(await first).toEqual(bitmap(1));
  });
  it("chyba modulu odmítne load se zprávou a paint s ním", async () => {
    const { worker, sent } = fakeWorker();
    const host = new CodeAnimationHost(() => worker);
    const loaded = host.load("bad");
    const painted = host.paint(req(0));
    worker.reply({ type: "error", id: sent[0].id, message: "Unexpected token" });
    await expect(loaded).rejects.toThrow("Unexpected token");
    await expect(painted).rejects.toThrow("Unexpected token");
  });
  it("chyba paint odmítne jen ten snímek a fronta jede dál", async () => {
    const { worker, sent } = fakeWorker();
    const host = new CodeAnimationHost(() => worker);
    const loaded = host.load("ok");
    worker.reply({ type: "loaded", id: sent[0].id });
    await loaded;
    const a = host.paint(req(1));
    await tick();
    worker.reply({ type: "error", id: sent[1].id, message: "paint selhal: x" });
    await expect(a).rejects.toThrow("paint selhal");
  });
  it("nad limit fronty zahodí nejstarší a dispose uvolní čekající", async () => {
    const { worker } = fakeWorker();
    const host = new CodeAnimationHost(() => worker);
    host.load("ok");
    const jobs = Array.from({ length: MAX_QUEUE + 1 }, (_, i) => host.paint(req(i)));
    expect(await jobs[0]).toBeNull();
    host.dispose();
    expect(await jobs[1]).toBeNull();
    expect(worker.terminated).toBe(true);
  });
  it("slow zavolá onSlow", () => {
    const { worker } = fakeWorker();
    const host = new CodeAnimationHost(() => worker);
    let ms = 0;
    host.onSlow = (v) => { ms = v; };
    worker.reply({ type: "slow", id: 1, ms: 80 });
    expect(ms).toBe(80);
  });
});
