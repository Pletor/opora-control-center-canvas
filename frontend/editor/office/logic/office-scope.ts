import type { Graph } from "@/shared/types/logic/types";
import type { WorkScope } from "@/shared/work-scope/logic/work-scope";
import { buildOffice, deskOf, type OfficeInput, type Office } from "./office-model";

/** Filter by problem identity before arranging rooms. Parent sectors only provide location. */
export function officeInScope(input: OfficeInput, scope: WorkScope): OfficeInput {
 if (scope.nodeId === null) return input;
 const members=new Set([scope.nodeId]);
 for (let i=0;i<input.graph.nodes.length;i++) {
  const before=members.size;
  for (const node of input.graph.nodes) if (node.parentId && members.has(node.parentId)) members.add(node.id);
  if (members.size===before) break;
 }
 const seen=new Set<string>();
 const tickets=input.tickets.filter(ticket => {
  const relevant=!!ticket.machine.cardId && members.has(ticket.machine.cardId) || ticket.machine.affectedNodeIds?.some(id=>members.has(id));
  if (!relevant || seen.has(ticket.ticketId)) return false;
  seen.add(ticket.ticketId);return true;
 });
 const shown=new Set([...members,...tickets.flatMap(ticket=>ticket.machine.cardId?[ticket.machine.cardId]:[])]);
 const byId=new Map(input.graph.nodes.map(node=>[node.id,node]));
 for (const id of [...shown]) {
  let parent=byId.get(id)?.parentId;
  const walked=new Set<string>();
  while (parent && !walked.has(parent)) { walked.add(parent);shown.add(parent);parent=byId.get(parent)?.parentId; }
 }
 const graph:Graph={nodes:input.graph.nodes.filter(node=>shown.has(node.id)),edges:input.graph.edges.filter(edge=>shown.has(edge.source)&&shown.has(edge.target))};
 return {...input,graph,tickets};
}

/** Loose cards in a nested context still get a desk, without inventing stored sector identities. */
export function scopedOffice(input: OfficeInput, scope: WorkScope): Office {
 const projected=officeInScope(input,scope);
 const office=buildOffice(projected);
 if (scope.nodeId===null) return office;
 const placed=new Set([...office.hall,...office.departments.flatMap(department=>department.rooms)].flatMap(room=>room.desks.map(desk=>desk.id)));
 const loose=projected.graph.nodes.filter(node=>node.kind==="node"&&!placed.has(node.id));
 const owner=projected.graph.nodes.find(node=>node.id===scope.nodeId);
 if (!loose.length || !owner) return office;
 const workers=office.reception;
 const desks=loose.map(node=>({...deskOf(node,projected),workers:workers.filter(worker=>worker.nodeId===node.id)}));
 const tones={ok:0,run:0,warn:0,fail:0,idle:0};for(const desk of desks) tones[desk.state.tone]++;
 const assigned=new Set(desks.flatMap(desk=>desk.workers.map(worker=>worker.id)));
 return {...office,reception:office.reception.filter(worker=>!assigned.has(worker.id)),hall:[...office.hall,{id:owner.id,name:owner.name,purpose:owner.purpose,tones,desks,common:[]}]};
}
