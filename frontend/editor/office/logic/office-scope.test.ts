import { expect, it } from "vitest";
import { officeInScope, scopedOffice } from "./office-scope";
import { emptyDesktopState } from "@/shared/desktop-state/logic/types";
import type { Graph } from "@/shared/types/logic/types";
import type { OfficeTicket } from "./office-model";
const n=(id:string,parentId:string|null,kind:"node"|"sector"="node")=>({id,parentId,kind,name:id,purpose:"",x:0,y:0});
const graph:Graph={nodes:[n("root",null,"sector"),n("login","root"),n("child","login"),n("tenant","root"),n("task",null)],edges:[]};
const t=(id:string,cardId:string,affectedNodeIds:string[]=[]):OfficeTicket=>({ticketId:id,status:"claimed",sessionId:id,updatedAt:"",body:{build:id},machine:{cardId,affectedNodeIds}});
it("projects one task into relevant scopes without copying it or showing unrelated rooms",()=>{
 const shared=t("shared","task",["login","tenant"]);
 const input={graph,state:emptyDesktopState(),tickets:[t("login-work","login"),t("tenant-work","tenant"),shared,shared,t("child-work","child")]};
 const login=officeInScope(input,{projectId:"p",nodeId:"login"});
 expect(login.tickets.map(ticket=>ticket.ticketId)).toEqual(["login-work","shared","child-work"]);
 expect(login.tickets[1]).toBe(shared);
 expect(login.graph.nodes.some(node=>node.id==="tenant")).toBe(false);
 expect(login.graph.nodes.some(node=>node.id==="root")).toBe(true);
 const tenant=officeInScope(input,{projectId:"p",nodeId:"tenant"});
 expect(tenant.tickets.map(ticket=>ticket.ticketId)).toEqual(["tenant-work","shared"]);
 expect(officeInScope(input,{projectId:"p",nodeId:null})).toBe(input);
});
it("gives a loose scoped card its existing worker once and keeps global office behavior",()=>{
 const input={graph:{nodes:[n("task",null)],edges:[]},state:emptyDesktopState(),tickets:[t("worker","task")]};
 const scoped=scopedOffice(input,{projectId:"p",nodeId:"task"});
 expect(scoped.hall[0].desks[0].id).toBe("task");
 expect(scoped.hall[0].desks[0].workers.map(worker=>worker.id)).toEqual(["worker"]);
 expect(scoped.reception).toEqual([]);
 expect(scopedOffice(input,{projectId:"p",nodeId:null}).reception[0].id).toBe("worker");
});
