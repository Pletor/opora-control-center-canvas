import { describe, expect, it } from "vitest";
import { DEFAULT_VOICE_PREFS, parseVoicePrefs } from "./voice-prefs";

describe("completion preferences", () => {
  it("keeps existing choices and gives old installations eight seconds", () => {
    expect(parseVoicePrefs('{"conversation":true,"voice":true,"ttsVoice":"browser","bargeIn":false}'))
      .toEqual({ conversation: true, voice: true, ttsVoice: "browser", bargeIn: false, endpointMs: 8000 });
    expect(parseVoicePrefs(null)).toEqual(DEFAULT_VOICE_PREFS);
  });
  it.each([0, 4000, 8000, 12000])("preserves supported completion %s", endpointMs => {
    expect(parseVoicePrefs(JSON.stringify({ endpointMs })).endpointMs).toBe(endpointMs);
  });
  it.each([-1, 1, 1000, 16000, "0", "4000", null, true])("rejects invalid completion %s", endpointMs => {
    expect(parseVoicePrefs(JSON.stringify({ endpointMs })).endpointMs).toBe(8000);
  });
});
