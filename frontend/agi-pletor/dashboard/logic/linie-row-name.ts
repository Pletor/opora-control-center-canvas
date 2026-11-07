/** Jméno řádku jako v prototypu: poslední segment větve (za posledním `-` nebo `/`) je tučně, zbytek je ztlumený prefix; lidský název s mezerou se neláme. */
export function splitRowName(text: string): { prefix: string; last: string } {
  const at = /\s/.test(text) ? -1 : Math.max(text.lastIndexOf("-"), text.lastIndexOf("/"));
  return at < 0 || at === text.length - 1 ? { prefix: "", last: text } : { prefix: text.slice(0, at + 1), last: text.slice(at + 1) };
}
