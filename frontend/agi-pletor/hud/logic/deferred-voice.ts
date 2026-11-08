import type { PletorMessage } from "./pletor-client";
import { proactiveReply } from "./proactive-reply";

export type DeferredSpeech = { text: string; spoken: boolean };
/** Remember announcements while a thought is unfinished; consuming happens only when audio can start. */
export function createDeferredVoice() {
  let seen: string | null | undefined;
  const pending: DeferredSpeech[] = [];
  return {
    observe(messages: PletorMessage[], loaded: boolean) {
      if (!loaded) { seen = undefined; pending.length = 0; return; }
      if (seen === undefined) { seen = proactiveReply(messages, seen).key; return; }
      const previous = messages.findIndex(message => `${message.at}\n${message.text}` === seen);
      // Polling may append several announcements at once; preserve each in chronological order.
      const start = previous < 0 && seen !== null ? Math.max(0, messages.length - 1) : previous + 1;
      for (let index = start; index < messages.length; index++) {
        const result = proactiveReply(messages.slice(0, index + 1), seen);
        seen = result.key;
        if (result.speak) pending.push({ text: result.speak.text, spoken: false });
      }
    },
    add: (speech: DeferredSpeech) => pending.push(speech),
    next: (blocked: boolean) => blocked ? undefined : pending.shift(),
    clear: () => { pending.length = 0; },
  };
}
