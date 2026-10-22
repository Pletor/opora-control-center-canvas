import { browserReaderEnvironment, emptyAgentState, watchAgentState, type AgentStateSnapshot, type ReaderEnvironment } from "./agent-state-reader";

// Jedno sdílené čtení agent-state pro celý prostor: přehled OporaHubu i odznaky na plátně Editoru
// odebírají stejný poller (jeden ETag, jeden dotaz za 10 s). Poslední odběratel čtení zastaví.
type Listener = (snapshot: AgentStateSnapshot) => void;
type Entry = { reader: ReturnType<typeof watchAgentState>; listeners: Set<Listener>; latest: AgentStateSnapshot };
type Watch = typeof watchAgentState;

export function createAgentStateStore(environment: () => ReaderEnvironment = browserReaderEnvironment, watch: Watch = watchAgentState) {
  const entries = new Map<string, Entry>();
  return {
    subscribe(project: string, workspace: string, listener: Listener) {
      const key = JSON.stringify([project, workspace]);
      let entry = entries.get(key);
      if (!entry) {
        const created: Entry = { listeners: new Set(), latest: emptyAgentState(), reader: undefined as unknown as Entry["reader"] };
        entries.set(key, created);
        created.reader = watch(project, workspace, next => { created.latest = next; created.listeners.forEach(item => item(next)); }, environment());
        entry = created;
      }
      const current = entry;
      current.listeners.add(listener);
      listener(current.latest);
      return {
        refresh: () => current.reader.refresh(),
        close: () => {
          current.listeners.delete(listener);
          if (!current.listeners.size && entries.get(key) === current) { entries.delete(key); current.reader.close(); }
        },
      };
    },
    size: () => entries.size,
  };
}

export const agentStateStore = createAgentStateStore();
