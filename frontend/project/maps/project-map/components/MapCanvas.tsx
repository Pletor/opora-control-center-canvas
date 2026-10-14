import {useEffect,useRef} from 'react';
import {panBy,shortLabel,zoomAt,type Bubble,type Community,type CommunityId,type Line,type View} from '@/project/maps/project-map/logic/project-map-model';

type Props={
  layout:Bubble[];lines:Line[];byId:Map<string,{community:Community;tone:number}>;
  selected:CommunityId|null;matches:Set<string>|null;view:View;base:View;
  onSelect:(id:CommunityId|null)=>void;onView:(view:View)=>void;
};

/** SVG plátno: bubliny komunit a čáry vazeb. Kolečko přibližuje kolem kurzoru, tah posouvá, klik vybírá. */
export default function MapCanvas({layout,lines,byId,selected,matches,view,base,onSelect,onView}:Props){
  const svg=useRef<SVGSVGElement>(null),drag=useRef<{x:number;y:number;moved:boolean;hit:string|null}|null>(null);
  const latest=useRef({view,base,onView});latest.current={view,base,onView};
  function toMap(clientX:number,clientY:number){
    const element=svg.current,matrix=element?.getScreenCTM();
    if(!element||!matrix)return {x:0,y:0};
    const point=element.createSVGPoint();point.x=clientX;point.y=clientY;
    const mapped=point.matrixTransform(matrix.inverse());return {x:mapped.x,y:mapped.y};
  }
  useEffect(()=>{
    const element=svg.current;if(!element)return;
    // Nativní posluchač, protože React registruje wheel jako pasivní a stránka by se jinak posouvala.
    const wheel=(event:WheelEvent)=>{event.preventDefault();const {view,base,onView}=latest.current;const p=toMap(event.clientX,event.clientY);onView(zoomAt(view,event.deltaY>0?1.15:1/1.15,p.x,p.y,base))};
    element.addEventListener('wheel',wheel,{passive:false});return()=>element.removeEventListener('wheel',wheel);
  },[]);
  const scale=base.w/view.w,key=selected==null?null:String(selected);
  return <svg ref={svg} className="project-map-canvas" viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`} role="img" aria-label="Mapa oblastí kódu"
    onPointerDown={event=>{
      // Zásah se čte hned při stisku; po zachycení ukazatele by pointerup mířil už jen na celé SVG.
      const hit=(event.target as Element).closest('[data-community]')?.getAttribute('data-community')??null;
      drag.current={x:event.clientX,y:event.clientY,moved:false,hit};event.currentTarget.setPointerCapture(event.pointerId)}}
    onPointerMove={event=>{const start=drag.current;if(!start)return;
      if(Math.hypot(event.clientX-start.x,event.clientY-start.y)>3)start.moved=true;if(!start.moved)return;
      const a=toMap(start.x,start.y),b=toMap(event.clientX,event.clientY);start.x=event.clientX;start.y=event.clientY;onView(panBy(view,b.x-a.x,b.y-a.y))}}
    onPointerUp={event=>{const start=drag.current;drag.current=null;if(start?.moved)return;
      onSelect(start?.hit?byId.get(start.hit)?.community.id??null:null)}}
    onPointerCancel={()=>{drag.current=null}}>
    <g className="project-map-canvas__lines">
      {lines.map(line=>{const touches=key!=null&&(String(line.source)===key||String(line.target)===key);
        return <line key={line.source+'-'+line.target} className={'project-map-canvas__line'+(touches?' project-map-canvas__line--active':key!=null?' project-map-canvas__line--muted':'')}
          x1={line.x1} y1={line.y1} x2={line.x2} y2={line.y2} strokeWidth={line.width/Math.sqrt(scale)}/>})}
    </g>
    {layout.map(bubble=>{const entry=byId.get(String(bubble.id));if(!entry)return null;
      const id=String(bubble.id),active=id===key,dim=matches!=null&&!matches.has(id);
      const showName=active||bubble.r*scale>=22,fontSize=12/scale;
      return <g key={id} data-community={id} className={'project-map-canvas__bubble project-map-canvas__bubble--tone-'+entry.tone+(active?' project-map-canvas__bubble--selected':'')+(dim?' project-map-canvas__bubble--dim':'')}>
        <title>{entry.community.name} · {entry.community.size} uzlů</title>
        <circle cx={bubble.x} cy={bubble.y} r={bubble.r}/>
        {bubble.r*scale>=12&&<text className="project-map-canvas__size" x={bubble.x} y={bubble.y} fontSize={Math.min(bubble.r*0.6,fontSize*1.1)}>{entry.community.size}</text>}
        {showName&&<text className="project-map-canvas__name" x={bubble.x} y={bubble.y+bubble.r+fontSize*1.1} fontSize={fontSize}>{shortLabel(entry.community.name,Math.max(14,Math.round(bubble.r*scale/3.5)))}</text>}
      </g>})}
  </svg>;
}
