import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import KnowledgeDrawer, { knowledgeAvailable } from "./KnowledgeDrawer";
import type { WorkspaceMode } from "@/shared/types/logic/workspace-mode";
const props={open:true,mode:"structure" as WorkspaceMode,scope:{projectId:"ample",nodeId:"login"},workspace:"work",projects:[{id:"ample",name:"AMPLE"}],onClose:()=>{}};
it("offers exactly one shared knowledge panel in every local view, preserving scope across tabs",()=>{
 for (const mode of ["structure","text","drawing","research","storyboard","office"] as WorkspaceMode[]) {
  expect(knowledgeAvailable(mode)).toBe(true);
  const html=renderToStaticMarkup(createElement(KnowledgeDrawer,{...props,mode}));
  expect(html).toContain('data-work-scope="login"');
  expect(html.match(/class="research-knowledge"/g)?.length).toBe(1);
 }
 expect(renderToStaticMarkup(createElement(KnowledgeDrawer,{...props,mode:"map"}))).toBe("");
 expect(renderToStaticMarkup(createElement(KnowledgeDrawer,{...props,open:false}))).toBe("");
 expect(renderToStaticMarkup(createElement(KnowledgeDrawer,{...props,scope:{projectId:"ample",nodeId:"tenant"}}))).toContain('data-work-scope="tenant"');
});
