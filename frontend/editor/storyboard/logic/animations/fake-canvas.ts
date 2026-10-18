// Testovací pomocník: falešný 2D kontext, který přijme jakékoli volání a zapamatuje si názvy volaných metod.
// Prostředí testů (node) canvas nemá; `paint` se tak dá ověřit, že nespadne a něco nakreslí.
export function fakeContext(): { ctx: CanvasRenderingContext2D; calls: string[] } {
  const calls: string[] = [];
  const store: Record<string, unknown> = {};
  const ctx = new Proxy(store, {
    get(target, prop: string) {
      if (prop in target) return target[prop];
      return (...args: unknown[]) => {
        calls.push(prop);
        if (prop === "createRadialGradient" || prop === "createLinearGradient") return { addColorStop() {} };
        if (prop === "measureText") return { width: String(args[0]).length * 8 };
        return undefined;
      };
    },
    set(target, prop: string, value) { target[prop] = value; return true; },
  }) as unknown as CanvasRenderingContext2D;
  return { ctx, calls };
}
