type Item = Record<string, unknown>;
export const object = (value: unknown): Item => value && typeof value === 'object' && !Array.isArray(value) ? value as Item : {};
const array = (value: unknown): unknown[] => Array.isArray(value) ? value : [];
const canonical = (value: unknown): string => JSON.stringify(Array.isArray(value) ? value.map(canonical)
  : value && typeof value === 'object' ? Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => [key, canonical(item)])) : value);
const indexed = (value: unknown) => new Map(array(value).map(item => [String(object(item).id), object(item)]));
export function changes(before: unknown, after: unknown) {
  const old = indexed(before), next = indexed(after);
  return [...new Set([...old.keys(), ...next.keys()])].filter(id => canonical(old.get(id)) !== canonical(next.get(id)))
    .map(id => ({id, before: old.get(id), after: next.get(id), action: !old.has(id) ? 'Přidání' : !next.has(id) ? 'Odstranění' : 'Úprava'}));
}
const changedKeys = (before: unknown, after: unknown) => [...new Set([...Object.keys(object(before)), ...Object.keys(object(after))])]
  .filter(key => canonical(object(before)[key]) !== canonical(object(after)[key])).length;
export function impact(before: unknown, after: unknown) {
  const old = object(before), next = object(after), oldGraph = object(old.graph), nextGraph = object(next.graph);
  const rawState = object(old.state), oldState = object(rawState.state ?? old.state), nextState = object(next.state);
  const oldRows = array(old.workspaceRows), nextRows = array(next.workspaceRows);
  const oldSet = new Set(oldRows.map(canonical)), nextSet = new Set(nextRows.map(canonical));
  return {nodes: changes(oldGraph.nodes, nextGraph.nodes), edges: changes(oldGraph.edges, nextGraph.edges),
    stateNodes: changedKeys(oldState.nodes, nextState.nodes), stateEdges: changedKeys(oldState.edges, nextState.edges),
    rules: changes(oldState.rules, nextState.rules).length, decisions: changes(oldState.decisions, nextState.decisions).length,
    workspaceRemoved: oldRows.filter(row => !nextSet.has(canonical(row))).length,
    workspaceAdded: nextRows.filter(row => !oldSet.has(canonical(row))).length,
    projectArchive: next.archived === true, oldNodeCount: array(oldGraph.nodes).length, nextNodeCount: array(nextGraph.nodes).length};
}
