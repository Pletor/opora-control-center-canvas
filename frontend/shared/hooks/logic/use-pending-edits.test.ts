import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "@/shared/types/logic/types";
import { clearPendingEdit, editScope, persistPendingEdit, readPendingEdit, writePendingEdit } from "./use-pending-edits";
vi.mock("@/shared/types/logic/types", () => ({ api: vi.fn() }));
const keys: string[] = [];
const key = (kind = "node-text") => { const value = editScope(kind, ["save-test", "draft", crypto.randomUUID()]); keys.push(value); return value; };
afterEach(() => { keys.forEach((value) => clearPendingEdit(value)); keys.length = 0; vi.resetAllMocks(); });

describe("shared pending CAS writer", () => {
  it("keeps an unmounted draft and its original revision on conflict", async () => {
    const scope = key(); writePendingEdit(scope, { text: "my text", revision: 4 });
    vi.mocked(api).mockRejectedValueOnce(new Error("Konflikt"));
    await expect(persistPendingEdit(scope)).rejects.toThrow("Konflikt");
    expect(readPendingEdit(scope)).toEqual({ text: "my text", revision: 4 });
    expect(api).toHaveBeenCalledWith("/api/node-text", expect.objectContaining({ expected_revision: 4, text: "my text" }));
  });
  it("clears only the accepted draft and rebases typing that arrived during a write", async () => {
    const scope = key(); writePendingEdit(scope, { text: "first", revision: 1 });
    let finish!: (value: { revision: number }) => void;
    vi.mocked(api).mockImplementationOnce(() => new Promise((resolve) => { finish = resolve as typeof finish; }));
    const save = persistPendingEdit(scope);
    writePendingEdit(scope, { text: "second", revision: 1 }); finish({ revision: 2 }); await save;
    expect(readPendingEdit(scope)).toEqual({ text: "second", revision: 2 });
    vi.mocked(api).mockResolvedValueOnce({ revision: 3 }); await persistPendingEdit(scope);
    expect(readPendingEdit(scope)).toBeNull();
  });
  it("serializes concurrent save requests for the same content", async () => {
    const scope = key(); writePendingEdit(scope, { text: "one", revision: 1 });
    let finish!: (value: { revision: number }) => void;
    vi.mocked(api).mockImplementationOnce(() => new Promise((resolve) => { finish = resolve as typeof finish; }));
    const first = persistPendingEdit(scope); const second = persistPendingEdit(scope);
    finish({ revision: 2 }); await Promise.all([first, second]);
    expect(api).toHaveBeenCalledTimes(1); expect(readPendingEdit(scope)).toBeNull();
  });
  it("preserves the root document's settings revision instead of silently accepting a newer target", async () => {
    const scope = editScope("workspace-document", ["save-test", "draft", ""]); keys.push(scope);
    writePendingEdit(scope, { text: JSON.stringify({ fields: { goal: "my goal" }, settingsRevision: 7 }), revision: 2 });
    vi.mocked(api).mockResolvedValueOnce({ nodeId: null }).mockRejectedValueOnce(new Error("Konflikt cíle"));
    await expect(persistPendingEdit(scope)).rejects.toThrow("Konflikt cíle");
    expect(api).toHaveBeenLastCalledWith("/api/workspace/document", expect.objectContaining({ expectedRevision: 2, expectedSettingsRevision: 7 }));
    expect(readPendingEdit(scope)).not.toBeNull();
  });
});
