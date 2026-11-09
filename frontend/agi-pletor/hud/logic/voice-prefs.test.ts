import { afterEach, describe, expect, it, vi } from "vitest";
import { DEFAULT_VOICE_PREFS, parseVoicePrefs, writeVoicePrefs } from "./voice-prefs";

describe("completion preferences", () => {
  afterEach(() => vi.unstubAllGlobals());
  it("keeps other choices and migrates old installations to explicit completion", () => {
    expect(parseVoicePrefs('{"conversation":true,"voice":true,"ttsVoice":"browser","bargeIn":false}'))
      .toEqual({ conversation: true, voice: true, ttsVoice: "browser", bargeIn: false, endpointMs: 0 });
    expect(parseVoicePrefs(null)).toEqual(DEFAULT_VOICE_PREFS);
  });
  it.each([0, 4000, 8000, 12000])("preserves supported completion %s", endpointMs => {
    expect(parseVoicePrefs(JSON.stringify({ endpointMs, completionVersion: 2 })).endpointMs).toBe(endpointMs);
    expect(parseVoicePrefs(JSON.stringify({ endpointMs })).endpointMs).toBe(0);
  });
  it.each([-1, 1, 1000, 16000, "0", "4000", null, true])("rejects invalid completion %s", endpointMs => {
    expect(parseVoicePrefs(JSON.stringify({ endpointMs, completionVersion: 2 })).endpointMs).toBe(0);
  });
  it("persists newly chosen timed completion with its version marker", () => {
    const setItem = vi.fn(); vi.stubGlobal("localStorage", { setItem });
    writeVoicePrefs({ ...DEFAULT_VOICE_PREFS, endpointMs: 12000 });
    const saved = setItem.mock.calls[0][1];
    expect(JSON.parse(saved).completionVersion).toBe(2);
    expect(parseVoicePrefs(saved).endpointMs).toBe(12000);
  });
});
