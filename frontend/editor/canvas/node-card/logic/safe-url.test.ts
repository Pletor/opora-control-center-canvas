import { expect, it } from "vitest";
import { safeLinkUrl } from "./safe-url";

it("accepts plain http(s) links", () => {
  expect(safeLinkUrl("https://example.com/log")).toBe(true);
  expect(safeLinkUrl("http://example.com/log")).toBe(true);
});

it.each(["javascript:alert(1)", "data:text/html,hi", "//example.com/x", "https://user:secret@example.com", "https://example.com:bad/x", "https://example.com/\nx", "https://example.com\\x", ""])("rejects unsafe link %s", url => {
  expect(safeLinkUrl(url)).toBe(false);
});
