/** Match backend route comparison without rewriting saved route spelling. */
export function pagePathKey(path: string): string {
  if (!path.startsWith("/") || [...path].length > 2048) throw new Error("Cesta stránky musí začínat / a mít nejvýše 2048 znaků.");
  let decoded: string;
  try {
    // Python unquote leaves a literal/malformed % intact, but rejects invalid UTF-8.
    decoded = decodeURIComponent(path.replace(/%(?![0-9a-f]{2})/gi, "%25"));
  } catch { throw new Error("Cesta stránky obsahuje neplatné kódování."); }
  if (decoded.includes("//") || /[\x00-\x20\\?#]/.test(decoded) || decoded.split("/").some((part) => part === "." || part === "..")) {
    throw new Error("Použijte cestu bez mezer, parametrů, #, dvojitého / a segmentů . nebo ..; například /kontakt.");
  }
  return decoded.replace(/\/+$/, "") || "/";
}

/** Normalize only an explicitly submitted draft; never run across stored nodes. */
export function normalizePagePath(raw: string): string {
  const value = raw.trim();
  if (!value) throw new Error("Vyplňte cestu stránky, například /kontakt nebo / pro úvodní stránku.");
  if (/^[a-z][a-z0-9+.-]*:/i.test(value) || value.startsWith("//")) throw new Error("Zadejte pouze cestu stránky, například /kontakt, bez https:// a domény.");
  const path = value.startsWith("/") ? value : `/${value}`;
  pagePathKey(path);
  return path;
}
