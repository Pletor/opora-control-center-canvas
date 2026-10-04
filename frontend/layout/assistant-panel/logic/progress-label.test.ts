import { describe, expect, it } from "vitest";
import { progressLabel } from "./progress-label";

describe("progressLabel", () => {
  it("přemýšlení ukáže velikost v kB", () => {
    expect(progressLabel({ kind: "thinking", chars: 2600, name: null })).toBe("Přemýšlí… 3 kB");
  });
  it("vstup nástroje nese jméno nástroje", () => {
    expect(progressLabel({ kind: "tool_input", chars: 24400, name: "Write" })).toBe("Píše Write… 24 kB");
  });
  it("bez jména řekne nástroj", () => {
    expect(progressLabel({ kind: "tool_input", chars: 2000, name: null })).toBe("Píše nástroj… 2 kB");
  });
});
