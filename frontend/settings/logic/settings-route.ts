export function settingsRequested(query: URLSearchParams): boolean {
  return query.get("screen") === "settings" || query.get("entry") === "settings";
}

/** Preserve the underlying workspace when reloading a settings link. */
export function underlyingScreen(query: URLSearchParams): "home" | "canvas" | "heart" {
  const screen = query.get("screen") === "settings" ? query.get("returnScreen") ?? "home" : query.get("screen");
  if (screen === "home" || screen === "heart" || screen === "canvas") return screen;
  return ["mode", "layer", "workspace"].some((key) => query.has(key)) ? "canvas" : "home";
}
