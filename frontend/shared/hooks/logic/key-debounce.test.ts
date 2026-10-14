import { afterEach, describe, expect, it, vi } from "vitest";
import { createKeyDebouncer } from "./key-debounce";

afterEach(() => vi.useRealTimers());

describe("createKeyDebouncer", () => {
  it("sloučí dávku změn klíčů do jednoho obnovení", () => {
    vi.useFakeTimers();
    const fire = vi.fn();
    const debouncer = createKeyDebouncer([1], 400, fire);
    debouncer.push([2]); vi.advanceTimersByTime(100);
    debouncer.push([3]); vi.advanceTimersByTime(100);
    debouncer.push([4]);
    expect(fire).not.toHaveBeenCalled();
    vi.advanceTimersByTime(399);
    expect(fire).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(fire).toHaveBeenCalledTimes(1);
  });
  it("stejné klíče nespustí nic", () => {
    vi.useFakeTimers();
    const fire = vi.fn();
    const debouncer = createKeyDebouncer([5], 400, fire);
    debouncer.push([5]); vi.advanceTimersByTime(1000);
    expect(fire).not.toHaveBeenCalled();
  });
  it("cancel zruší čekající obnovení", () => {
    vi.useFakeTimers();
    const fire = vi.fn();
    const debouncer = createKeyDebouncer([1], 400, fire);
    debouncer.push([2]); debouncer.cancel(); vi.advanceTimersByTime(1000);
    expect(fire).not.toHaveBeenCalled();
  });
});
