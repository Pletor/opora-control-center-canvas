// Žádost o výběr existujícího úkolu zvenku panelu (živý panel domény: klik na čip relace asistenta).
// App ji předá s pořadovým číslem; panel úkol vybere, jakmile ho má v seznamu (seznam se načítá
// pollingem, takže hned po otevření tam ještě být nemusí). Každá žádost se splní nejvýš jednou.

export type SelectRequest = { seq: number; sessionId: string };

/** ID úkolu k výběru, nebo `null`, když žádost už byla vyřízená nebo úkol v seznamu ještě není. */
export function pendingSelection(request: SelectRequest | null | undefined, handledSeq: number, sessionIds: readonly string[]): string | null {
  if (!request || request.seq === handledSeq) return null;
  return sessionIds.includes(request.sessionId) ? request.sessionId : null;
}
