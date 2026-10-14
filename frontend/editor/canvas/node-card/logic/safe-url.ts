// Bezpečný odkaz z karty (důkaz, log, PR): jen http(s) s hostem, bez přihlašovacích údajů, řídicích znaků
// a zpětných lomítek. Jinak karta odkaz nevykreslí.
export function safeLinkUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return /^https?:\/\//i.test(value) && !!url.hostname && !url.username && !url.password &&
      !/[\s\\\u0000-\u001f]/.test(value) && value.length <= 2048;
  } catch { return false; }
}
