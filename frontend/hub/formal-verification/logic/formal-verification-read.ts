import { formalDetailUrl, formalQuery, FORMAL_ROOT, type FormalScope } from "./formal-verification";
import { parseFormalHistory, parseFormalRecord } from "./formal-verification-parse";
export type FormalReadApi = <T>(url: string) => Promise<T>;

export async function readFormalHistory(read: FormalReadApi, scope: FormalScope) {
  await read("/api/access/ui-session");
  return parseFormalHistory(await read<unknown>(`${FORMAL_ROOT}?${formalQuery(scope)}`), scope);
}
export async function readFormalDetail(read: FormalReadApi, scope: FormalScope, id: string) {
  const url = formalDetailUrl(scope, id);
  await read("/api/access/ui-session");
  return parseFormalRecord(await read<unknown>(url), scope, id);
}
