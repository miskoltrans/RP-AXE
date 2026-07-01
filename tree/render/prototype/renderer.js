// renderer.js — RP-AXE tech-tree rendering prototype (Canvas 2D).
//
// PORTABILITY LEDGER — everything here maps onto a KSP "enhance-stock" plugin (Vectrosity lines +
// arrow sprites + TextMeshPro), checked against decompiled RDNode / Vectrosity:
//   * each edge = ONE flat polyline (VectorLine, LineType.Continuous), uniform width, one flat colour.
//   * corners = pre-tessellated points (port of stock RDNode.chamferCorner) — NOT canvas arcs/beziers.
//   * arrowheads = one endpoint sprite per edge, snapped to 4 cardinal dirs (stock arrowT/B/L/R).
//   * state / highlight / dim = COLOUR + ALPHA only (Vectrosity line.color — cheap, no re-Draw).
//     NEVER vary width per state: a width change needs VectorLine.Draw() (mesh rebuild). This is
//     exactly stock's model — build once in DrawArrow, then only toggle active + swap material colour.
//   * geometry built ONCE (buildGeometry); draw() only transforms (pan/zoom) + recolours.
//   * node tile = a node Image (tint it by discipline); in-tile title/badge = child TMP labels
//     (stock shows only the RD icon there); contrast ink = the TMP colour.
// Cosmetic-only (achieved differently in KSP, harmless): canvas lineCap/lineJoin 'round' (KSP rounds
//   via the tessellated points, caps are square); dashed anyToUnlock via setLineDash (KSP = a dash
//   TEXTURE on the Material; colour is the real distinguisher); px sizes here vs grid-scaled in KSP.
// Scale: 1 VectorLine + 1 (pooled) arrow sprite per edge, 1–2 TMP labels per node — ~300 each at the
//   full tree, within KSP norms (RP-1 ships ~330 nodes). Pool/cull off-screen sprites + labels.
//
// World space = the cfg px space carried in tree-data.js (x = MARGIN_X + tier*TIERW, y = layout row).
'use strict';

// ---- tunables ----
const NODE_W = 168, NODE_H = 62;        // tile size in world units (tiers 430 apart, rows ~80 apart)
const CORNER_R = 15, CORNER_SEGS = 3;   // stock UIGridArea.roundedCornerRadius / lineCornerSegments
const EDGE_W = 2;                        // uniform stroke width (stock lineThickness=2); NEVER varied per state — width change = VectorLine.Draw rebuild
const ARROW = 9;                        // arrowhead size (screen px here; KSP arrow sprite scales with the grid transform)
const GOLD = '#f4d35e', GRAY = '#8a8f98';
const DIM_EDGE = 0.10, DIM_NODE = 0.24; // alpha for de-emphasised elements when a lineage is focused
const FAN_LO = 0.18, FAN_HI = 0.82;     // fraction range along a node side for distributed endpoints

// ---- vec helpers ----
const sub=(a,b)=>[a[0]-b[0],a[1]-b[1]], add=(a,b)=>[a[0]+b[0],a[1]+b[1]], mul=(a,k)=>[a[0]*k,a[1]*k];
const hyp=a=>Math.hypot(a[0],a[1]), norm=a=>{const l=hyp(a)||1;return [a[0]/l,a[1]/l];};

// ---- state ----
let D, byId={}, parents={}, children={}, edges=[];
let cam={s:1,x:0,y:0};                  // world->screen: screenX = worldX*s + x
let hoverId=null, selId=null, focusSet=null, litEdges=null;
let cv, ctx, DPR=window.devicePixelRatio||1;
const opt={ fan:true, arrows:true, discEdges:true, highlight:true, baseline:false, progress:true, lane:false, icons:true };
let researched=new Set();                      // research state (KSP RDNode.State: researched/researchable/locked)
const LSKEY='rpaxe-tree-progress';
const C_DONE='#4ade80', C_AVAIL='#38bdf8';     // researched / researchable (the frontier = "what to research next")
const EDGE_LOCK='#464b53', GOLD_DIM='#6f6535'; // prereq-not-met edge (stock LineMaterialGray)

// ============================ model ============================
function buildModel(){
  D=window.TREE;
  byId={}; parents={}; children={};
  for(const n of D.nodes){ byId[n.id]=n; parents[n.id]=[]; children[n.id]=[]; }
  edges=D.edges.map(e=>({from:e.from,to:e.to,anyToUnlock:!!e.anyToUnlock,waypoints:e.waypoints}));
  for(const e of edges){
    if(!(e.from in byId)||!(e.to in byId)) continue;
    children[e.from].push(e.to); parents[e.to].push(e.from);
    e.discColor=(D.disciplines[byId[e.from].discipline]||{}).color||GRAY;
  }
}
function reachable(id, adj){                       // BFS closure (ancestors via parents / descendants via children)
  const seen=new Set(), st=[id];
  while(st.length){ const x=st.pop(); for(const y of adj[x]||[]) if(!seen.has(y)){ seen.add(y); st.push(y); } }
  return seen;
}

// ============================ progression (research state) ============================
// Mirrors KSP RDNode.State: RESEARCHED / RESEARCHABLE / LOCKED (no queue). The RESEARCHABLE frontier
// is "what you can research next". Fully portable: state is native KSP; edge lit-by-parent-researched
// = stock UpdateGraphics (LineMaterial vs LineMaterialGray); persistence = the save game.
const RESEARCHED='researched', RESEARCHABLE='researchable', LOCKED='locked';
function parentsSatisfied(id){
  const ps=parents[id]||[];
  if(!ps.length) return true;                                  // roots are researchable from the start
  return byId[id].anyToUnlock ? ps.some(p=>researched.has(p)) : ps.every(p=>researched.has(p));
}
function stateOf(id){ return researched.has(id) ? RESEARCHED : (parentsSatisfied(id) ? RESEARCHABLE : LOCKED); }
function research(id){ if(byId[id] && !researched.has(id) && parentsSatisfied(id)){ researched.add(id); persist(); return true; } return false; }
function unresearch(id){                                        // cascade: drop descendants that lose their prereqs
  if(!researched.delete(id)) return;
  let changed=true; while(changed){ changed=false;
    for(const r of [...researched]) if(!parentsSatisfied(r)){ researched.delete(r); changed=true; } }
  persist();
}
function researchPathTo(id){                                    // complete id + all unresearched prereqs, in dependency order
  const need=new Set([...reachable(id,parents), id]); let changed=true;
  while(changed){ changed=false; for(const n of need) if(!researched.has(n)&&parentsSatisfied(n)){ researched.add(n); changed=true; } }
  persist();
}
function resetProgress(){ researched.clear(); persist(); }
function counts(){ let r=0,a=0,l=0,sci=0;
  for(const n of D.nodes){ const s=stateOf(n.id);
    if(s===RESEARCHED){ r++; sci+=n.cost||0; } else if(s===RESEARCHABLE) a++; else l++; }
  return {r,a,l,sci,total:D.nodes.length}; }
function persist(){ try{ localStorage.setItem(LSKEY, JSON.stringify({r:[...researched]})); }catch(e){} }
function restore(){ try{ const s=JSON.parse(localStorage.getItem(LSKEY)||'{}');
  (s.r||[]).forEach(x=>{ if(byId[x]) researched.add(x); }); }catch(e){} }

// ============================ geometry ============================
function box(n){ return {x:n.pos[0], y:n.pos[1], w:NODE_W, h:NODE_H}; }
function anchor(n, side, t){                       // point on a node side; t in [0,1] along it (0.5 = centre)
  const b=box(n);
  if(side==='RIGHT')  return [b.x+b.w, b.y+t*b.h];
  if(side==='LEFT')   return [b.x,     b.y+t*b.h];
  if(side==='TOP')    return [b.x+t*b.w, b.y];
  return [b.x+t*b.w, b.y+b.h];                     // BOTTOM
}

// ENDPOINT DISTRIBUTION (the fan-in/out fix). Edges leave a node's RIGHT side and enter the next
// node's LEFT side; spread the slots along the side, ordered by the other end's Y so they don't cross.
// fan OFF -> every slot collapses to 0.5 (centre) = the stock convergence, for A/B comparison.
// -> KSP port: a Harmony hook on RDNode.GetPosition/DrawArrow computing the same per-edge offset.
function computeSlots(){
  const outB={}, inB={};
  for(const e of edges){
    if(!(e.from in byId)||!(e.to in byId)) continue;
    (outB[e.from]=outB[e.from]||[]).push(e);
    (inB[e.to]  =inB[e.to]  ||[]).push(e);
  }
  const spread=(list, cyOf, setT)=>{
    list.sort((a,b)=>cyOf(a)-cyOf(b));
    const n=list.length;
    list.forEach((e,i)=> setT(e, (!opt.fan||n<=1)?0.5 : FAN_LO+(FAN_HI-FAN_LO)*(i/(n-1))));
  };
  for(const id in outB) spread(outB[id], e=>byId[e.to].pos[1],   (e,t)=>e._tF=t);
  for(const id in inB)  spread(inB[id],  e=>byId[e.from].pos[1], (e,t)=>e._tT=t);
  for(const e of edges){ if(e._tF==null)e._tF=0.5; if(e._tT==null)e._tT=0.5; }
}

// Stock RDNode.chamferCorner: iterative corner-cutting -> 2^segs tessellated points, offsets r/2.5^(i+1).
function chamfer(inP, cor, outP, r, segs){
  let pts=[cor];
  for(let it=0; it<segs; it++){
    const np=[], d=r/Math.pow(2.5, it+1);
    for(let k=0;k<pts.length;k++){
      const v=pts[k], prev=k>0?pts[k-1]:inP, next=k<pts.length-1?pts[k+1]:outP;
      np.push(add(v, mul(norm(sub(prev,v)), d)));
      np.push(add(v, mul(norm(sub(next,v)), d)));
    }
    pts=np;
  }
  return pts;
}

// kspStock routing: RIGHT anchor of parent -> LEFT anchor of child (the stock L/R->L/R case):
// straight if same row, else an S with two rounded corners at the mid-X split.
function routeEdge(e){
  const p=anchor(byId[e.from],'RIGHT', e._tF), c=anchor(byId[e.to],'LEFT', e._tT);
  if(Math.abs(p[1]-c[1])<0.5) return [p,c];
  const mx=(p[0]+c[0])/2, k1=[mx,p[1]], k2=[mx,c[1]];
  return [p, ...chamfer(p,k1,k2,CORNER_R,CORNER_SEGS), ...chamfer(k1,k2,c,CORNER_R,CORNER_SEGS), c];
}
const snap4=d=> Math.abs(d[0])>=Math.abs(d[1]) ? [Math.sign(d[0])||1,0] : [0,Math.sign(d[1])||1];

// laneRouted: route through the layout's dummy waypoints; vertical legs spread into per-gutter lanes
// (interval-graph colouring) so parallel lines don't pile up. Consumes edges[].waypoints (layout-owned).
// Still one flat polyline per edge — the KSP port is a Harmony hook on GetVectorArray returning this
// richer point list instead of the stock elbow.
function buildLaneRoutes(){
  const xs=[...new Set(D.nodes.map(n=>n.pos[0]))].sort((a,b)=>a-b);
  const X0=xs[0], TW=xs.length>1?xs[1]-xs[0]:430;
  const tierOf=x=>Math.round((x-X0)/TW), tierX=t=>X0+t*TW;
  const seg={}, chains=[];
  for(const e of edges){
    if(!e.waypoints || e.waypoints.length<2){ e.laneGeom=null; continue; }
    const ts=e.waypoints.map(p=>tierOf(p[0])), ys=e.waypoints.map(p=>p[1]+NODE_H/2);
    chains.push([e,ts,ys]);
    for(let i=0;i<ts.length-1;i++)
      (seg[ts[i]]=seg[ts[i]]||[]).push([Math.min(ys[i],ys[i+1]),Math.max(ys[i],ys[i+1]),e.from+'>'+e.to+'#'+i]);
  }
  const lane={}, lanesN={};
  for(const g in seg){ const s=seg[g].sort((a,b)=>a[0]-b[0]), ends=[];
    for(const [lo,hi,key] of s){ let l=ends.findIndex(h=>h<=lo+1e-6); if(l<0){ l=ends.length; ends.push(hi); } else ends[l]=hi; lane[key]=l; }
    lanesN[g]=ends.length; }
  const laneX=(g,l)=>tierX(g)+NODE_W+(l+1)/(lanesN[g]+1)*(TW-NODE_W);
  for(const [e,ts,ys] of chains){
    const pts=[[tierX(ts[0])+NODE_W, ys[0]]];
    for(let i=0;i<ts.length-1;i++){ const lx=laneX(ts[i], lane[e.from+'>'+e.to+'#'+i]); pts.push([lx,ys[i]],[lx,ys[i+1]]); }
    pts.push([tierX(ts[ts.length-1]), ys[ys.length-1]]);
    e.laneGeom=pts;
  }
}

function buildGeometry(){
  computeSlots();
  buildLaneRoutes();
  for(const e of edges){
    if(!(e.from in byId)||!(e.to in byId)){ e.geom=null; continue; }
    e.geom = (opt.lane && e.laneGeom) ? e.laneGeom : routeEdge(e);   // laneRouted (waypoints) or stock elbow
    const a=e.geom[e.geom.length-1], b=e.geom[e.geom.length-2];
    e.arrow={ tip:a, dir:snap4(norm(sub(a,b))) };
  }
}

// ============================ view / draw ============================
const SX=wx=>wx*cam.s+cam.x, SY=wy=>wy*cam.s+cam.y;

function draw(){
  ctx.setTransform(DPR,0,0,DPR,0,0);
  ctx.clearRect(0,0,cv.width,cv.height);
  ctx.lineJoin='round'; ctx.lineCap='round';   // cosmetic — KSP rounds via tessellated chamfer pts; caps are square
  const focusing = !!(focusSet && opt.highlight);

  // tier column labels (orientation)
  ctx.fillStyle='#5a6673'; ctx.font='600 12px Segoe UI,Helvetica,Arial'; ctx.textAlign='left'; ctx.textBaseline='top';
  const tierX={}; for(const n of D.nodes){ if(!(n.tier in tierX)) tierX[n.tier]=n.pos[0]; }
  for(const t in tierX){ ctx.fillText('T'+t, SX(tierX[t]), 6); }

  // edges (under nodes)
  for(const e of edges){
    if(!e.geom) continue;
    const lit = !focusing || (litEdges && litEdges.has(e));
    const parentDone = researched.has(e.from);
    let color;
    if(opt.progress && !parentDone) color = e.anyToUnlock ? GOLD_DIM : EDGE_LOCK;   // prereq not researched yet (stock gray)
    else color = e.anyToUnlock ? GOLD : ((opt.discEdges && !opt.baseline) ? e.discColor : GRAY);
    ctx.globalAlpha = focusing ? (lit?1:DIM_EDGE) : 1;
    ctx.strokeStyle = color;
    ctx.lineWidth = EDGE_W;              // uniform; emphasis is colour+alpha only (no rebuild)
    ctx.setLineDash(e.anyToUnlock ? [6,4] : []);   // KSP: a dash-texture Material, not a numeric array
    const g=e.geom;
    ctx.beginPath(); ctx.moveTo(SX(g[0][0]),SY(g[0][1]));
    for(let i=1;i<g.length;i++) ctx.lineTo(SX(g[i][0]),SY(g[i][1]));
    ctx.stroke();
    ctx.setLineDash([]);
    if(opt.arrows) drawArrow(e.arrow, color, ctx.globalAlpha);
  }
  ctx.globalAlpha=1;

  for(const n of D.nodes) drawNode(n, focusing);
}

function drawArrow(ar, color, alpha){
  const t=[SX(ar.tip[0]),SY(ar.tip[1])], d=ar.dir, pp=[-d[1],d[0]];
  const base=[t[0]-d[0]*ARROW, t[1]-d[1]*ARROW];
  ctx.globalAlpha=alpha; ctx.fillStyle=color;
  ctx.beginPath();
  ctx.moveTo(t[0],t[1]);
  ctx.lineTo(base[0]+pp[0]*ARROW*0.6, base[1]+pp[1]*ARROW*0.6);
  ctx.lineTo(base[0]-pp[0]*ARROW*0.6, base[1]-pp[1]*ARROW*0.6);
  ctx.closePath(); ctx.fill();
}

function drawNode(n, focusing){
  const b=box(n), x=SX(b.x), y=SY(b.y), w=b.w*cam.s, h=b.h*cam.s;
  const disc=D.disciplines[n.discipline]||{color:'#888',title:n.discipline};
  const st = opt.progress ? stateOf(n.id) : null;
  const dimFocus = focusing && !focusSet.has(n.id);
  const alpha = dimFocus ? DIM_NODE : (st===LOCKED ? 0.5 : 1);   // locked = faded (stock FADED)
  ctx.globalAlpha = alpha;

  // NOTE(port): tile = a node Image tinted by discipline colour; title/badge = child TMP labels
  // (stock draws only the RD icon here); contrast ink below = the TMP colour.
  roundRect(x,y,w,h,Math.max(2,3*cam.s)); ctx.fillStyle=disc.color; ctx.fill();

  if(opt.progress && !dimFocus){                 // state ring — colour only (portable Image/line tint, no rebuild)
    const ring = st===RESEARCHED ? C_DONE : (st===RESEARCHABLE ? C_AVAIL : null);
    if(ring){ ctx.strokeStyle=ring; ctx.lineWidth=2.5; ctx.stroke(); }
  }
  if(n.id===selId){ ctx.strokeStyle='#fff'; ctx.lineWidth=3; ctx.stroke(); }
  else if(n.id===hoverId){ ctx.strokeStyle='rgba(255,255,255,.85)'; ctx.lineWidth=2; ctx.stroke(); }

  if(opt.icons && iconReady(disc.icon) && cam.s>0.15){   // discipline RD icon, top-left corner
    const s=Math.min(w,h)*0.4; ctx.globalAlpha=alpha;
    ctx.drawImage(iconImg[disc.icon], x+3*cam.s, y+3*cam.s, s, s);
  }

  const ink = lum(disc.color)>140 ? '#10181f' : '#f3f3f3';   // contrast text (fixes dark-on-dark)
  ctx.fillStyle=ink; ctx.textAlign='center'; ctx.textBaseline='middle';
  const fs=Math.max(7.5, 10.5*cam.s);
  if(fs>=6){
    ctx.font=`600 ${fs}px Segoe UI,Helvetica,Arial,sans-serif`;
    const maxw=w*0.9, lines=wrap(n.title,13,3).map(ln=>clip(ln,maxw));
    const lh=fs*1.13, top=y+h/2-(lines.length-1)*lh/2-4*cam.s;
    lines.forEach((ln,i)=> ctx.fillText(ln, x+w/2, top+i*lh));
    const np=(n.parts||[]).length, nu=(n.upgrades||[]).length;
    ctx.font=`${Math.max(6,8*cam.s)}px Segoe UI,Helvetica,Arial`;
    ctx.globalAlpha=alpha*0.75;
    ctx.fillText(`T${n.tier} · ${np?np+'p':'—'}${nu?'+'+nu+'u':''}`, x+w/2, y+h-8*cam.s);
  }
  if(opt.progress && !dimFocus && st===RESEARCHED && cam.s>0.2){    // ✓ researched
    ctx.globalAlpha=alpha; ctx.textBaseline='top'; ctx.fillStyle=C_DONE; ctx.textAlign='right';
    ctx.font=`bold ${Math.max(9,12*cam.s)}px Segoe UI`; ctx.fillText('✓', x+w-3, y+2);
  }
  ctx.globalAlpha=1;
}

function roundRect(x,y,w,h,r){
  r=Math.min(r,w/2,h/2);
  ctx.beginPath();
  ctx.moveTo(x+r,y); ctx.arcTo(x+w,y,x+w,y+h,r); ctx.arcTo(x+w,y+h,x,y+h,r);
  ctx.arcTo(x,y+h,x,y,r); ctx.arcTo(x,y,x+w,y,r); ctx.closePath();
}
function lum(hex){ const h=hex.replace('#',''); return 0.2126*parseInt(h.slice(0,2),16)+0.7152*parseInt(h.slice(2,4),16)+0.0722*parseInt(h.slice(4,6),16); }
function clip(s,maxw){ if(ctx.measureText(s).width<=maxw) return s; while(s.length>1 && ctx.measureText(s+'…').width>maxw) s=s.slice(0,-1); return s+'…'; }
function wrap(s,width,maxlines){
  const words=(s||'').trim().split(/\s+/), lines=[]; let cur='';
  for(const w of words){ const cand=cur?cur+' '+w:w;
    if(!cur||cand.length<=width) cur=cand;
    else { lines.push(cur); cur=w; if(lines.length===maxlines-1) break; } }
  if(cur) lines.push(cur);
  if(lines.length>maxlines){ lines[maxlines-1]=lines[maxlines-1].slice(0,width-1)+'…'; lines.length=maxlines; }
  return lines;
}
// node icons — RD sprite per discipline (KSP: the node's Image/icon). Loaded from icons/<disc.icon>.png.
const iconImg={};
function loadIcons(){ for(const nm of new Set(Object.values(D.disciplines).map(d=>d.icon).filter(Boolean))){
  const im=new Image(); im.onload=draw; im.src='icons/'+nm+'.png'; iconImg[nm]=im; } }
function iconReady(nm){ const im=iconImg[nm]; return im && im.complete && im.naturalWidth>0; }

// ============================ interaction ============================
function hitTest(mx,my){
  const wx=(mx-cam.x)/cam.s, wy=(my-cam.y)/cam.s;
  for(let i=D.nodes.length-1;i>=0;i--){ const n=D.nodes[i], b=box(n);
    if(wx>=b.x&&wx<=b.x+b.w&&wy>=b.y&&wy<=b.y+b.h) return n.id; }
  return null;
}
const activeFocus=()=> hoverId||selId;
function setFocus(id){
  if(!id||!opt.highlight){ focusSet=null; litEdges=null; return; }
  const anc=reachable(id,parents), desc=reachable(id,children);
  focusSet=new Set([id,...anc,...desc]);
  litEdges=new Set(edges.filter(e=>focusSet.has(e.from)&&focusSet.has(e.to)));
}
function fit(){
  const xs=D.nodes.map(n=>n.pos[0]), ys=D.nodes.map(n=>n.pos[1]);
  const x0=Math.min(...xs), x1=Math.max(...xs)+NODE_W, y0=Math.min(...ys), y1=Math.max(...ys)+NODE_H;
  const W=cv.clientWidth, H=cv.clientHeight, m=40;
  cam.s=Math.min((W-2*m)/(x1-x0), (H-2*m)/(y1-y0));
  cam.x=m-x0*cam.s + (W-2*m-(x1-x0)*cam.s)/2;
  cam.y=m-y0*cam.s + (H-2*m-(y1-y0)*cam.s)/2;
  updateZoomLabel();
}
function centerOn(id){ const n=byId[id]; if(!n)return; const b=box(n);
  cam.x=cv.clientWidth/2-(b.x+b.w/2)*cam.s; cam.y=cv.clientHeight/2-(b.y+b.h/2)*cam.s; }
function updateZoomLabel(){ const el=document.getElementById('zl'); if(el) el.textContent=Math.round(cam.s/fitScale*100)+'%'; }
let fitScale=1;

function resize(){
  const W=cv.clientWidth, H=cv.clientHeight;
  cv.width=W*DPR; cv.height=H*DPR; draw();
}

// ============================ panel ============================
const esc=s=>(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
function showPanel(id){
  const p=document.getElementById('panel'), d=byId[id];
  if(!d){ p.innerHTML='<div class="hint">Hover to trace a lineage · click to pin.</div>'+legendHTML(); return; }
  const disc=D.disciplines[d.discipline]||{}; const np=(d.parts||[]);
  let h=`<div class="ttl">${esc(d.title)}</div>`;
  h+=`<div class="meta"><span class="dot" style="background:${disc.color}"></span>${esc(disc.title||d.discipline)} · T${d.tier} · ${d.cost}◈${d.anyToUnlock?' · any-parent':''}</div>`;
  const ps=parents[id]||[], cs=children[id]||[];
  h+=`<div class="rel">↑ ${ps.length} prereq${ps.length!==1?'s':''} · ↓ ${cs.length} unlock${cs.length!==1?'s':''}</div>`;
  if(opt.progress){
    const st=stateOf(id);
    h+=`<div class="acts">`;
    if(st===RESEARCHED)        h+=`<button data-act="unresearch" data-id="${id}">Unresearch</button>`;
    else if(st===RESEARCHABLE) h+=`<button class="go" data-act="research" data-id="${id}">Research</button>`;
    else                       h+=`<button class="go" data-act="path" data-id="${id}">Research path to here</button>`;
    h+=`<span class="st st-${st}">${st}</span></div>`;
  }
  if(d.flavor) h+=`<div class="flav">${esc(d.flavor)}</div>`;
  h+=`<div class="sec">Parts (${np.length})</div>`;
  if(np.length){ h+='<ul class="parts">'; for(const q of np) h+=`<li><div class="pt">${esc(q.title||q.name)}</div><div class="pn">${esc(q.name)}${q.mod?' · <span class="mod">'+esc(q.mod)+'</span>':''}</div></li>`; h+='</ul>'; }
  else h+='<div class="empty">— no parts assigned —</div>';
  if((d.upgrades||[]).length){ h+=`<div class="sec">Upgrades (${d.upgrades.length})</div><ul class="parts">`; for(const u of d.upgrades) h+=`<li><div class="pn">${esc(u)}</div></li>`; h+='</ul>'; }
  p.innerHTML=h;
}
function legendHTML(){
  const ds=Object.values(D.disciplines).sort((a,b)=>a.order-b.order);
  let h='';
  if(opt.progress){
    h+=`<div class="sec">Research state</div><ul class="legend">`+
       `<li><span class="ring" style="border-color:${C_DONE}"></span>Researched</li>`+
       `<li><span class="ring" style="border-color:${C_AVAIL}"></span>Researchable — research next</li>`+
       `<li><span class="ring locked"></span>Locked (prereqs unmet)</li></ul>`;
  }
  h+=`<div class="sec">Disciplines</div><ul class="legend">`+
     ds.map(d=>`<li><span class="dot" style="background:${d.color}"></span>${esc(d.title)}</li>`).join('')+`</ul>`;
  return h;
}

// ============================ init ============================
function rebuild(){ buildGeometry(); draw(); }
function updateHud(){ const el=document.getElementById('hud'); if(!el)return;
  if(!opt.progress){ el.style.display='none'; return; } el.style.display='';
  const c=counts();
  el.innerHTML=`<b>${c.r}</b>/${c.total} researched · <span style="color:${C_AVAIL}">${c.a} available</span> · `+
               `<span style="color:#8a8f98">${c.l} locked</span> · ${c.sci.toLocaleString()}◈`;
}
function afterStateChange(){ draw(); updateHud(); if(selId) showPanel(selId); }
function init(){
  cv=document.getElementById('cv'); ctx=cv.getContext('2d');
  if(/baseline/.test(location.search)){ opt.baseline=true; opt.fan=false; opt.discEdges=false; opt.highlight=false; }
  if(new URLSearchParams(location.search).has('lane')) opt.lane=true;
  buildModel(); restore();
  const rq=new URLSearchParams(location.search).get('research');   // ?research=id,id — shareable snapshot / demo
  if(rq) rq.split(',').forEach(x=>{ if(byId[x]) researched.add(x); });
  buildGeometry(); loadIcons();
  new ResizeObserver(resize).observe(cv);
  cv.width=cv.clientWidth*DPR; cv.height=cv.clientHeight*DPR;
  fit(); fitScale=cam.s; updateZoomLabel();
  const selParam=new URLSearchParams(location.search).get('sel');
  if(selParam && byId[selParam]){ selId=selParam; setFocus(selId); centerOn(selId); showPanel(selId); }
  else showPanel(null);
  draw();

  // pan (drag) vs click
  let down=null, moved=false;
  cv.addEventListener('mousedown',e=>{ down={x:e.offsetX,y:e.offsetY,cx:cam.x,cy:cam.y}; moved=false; });
  window.addEventListener('mouseup',e=>{
    if(down && !moved){ selId=hitTest(down.x,down.y); setFocus(activeFocus()); showPanel(selId); draw(); }
    down=null;
  });
  cv.addEventListener('mousemove',e=>{
    if(down){ const dx=e.offsetX-down.x, dy=e.offsetY-down.y; if(Math.abs(dx)+Math.abs(dy)>3)moved=true;
      cam.x=down.cx+dx; cam.y=down.cy+dy; draw(); return; }
    const h=hitTest(e.offsetX,e.offsetY);
    cv.style.cursor=h?'pointer':'grab';
    if(h!==hoverId){ hoverId=h; setFocus(activeFocus()); draw(); }
  });
  cv.addEventListener('wheel',e=>{ e.preventDefault();
    const f=e.deltaY<0?1.12:1/1.12, mx=e.offsetX, my=e.offsetY;
    const wx=(mx-cam.x)/cam.s, wy=(my-cam.y)/cam.s;
    cam.s=Math.max(0.05,Math.min(6,cam.s*f)); cam.x=mx-wx*cam.s; cam.y=my-wy*cam.s;
    updateZoomLabel(); draw();
  },{passive:false});

  cv.addEventListener('dblclick',e=>{ const id=hitTest(e.offsetX,e.offsetY); if(!id||!opt.progress)return;
    const s=stateOf(id);
    if(s===RESEARCHABLE) research(id); else if(s===RESEARCHED) unresearch(id); else researchPathTo(id);
    selId=id; setFocus(activeFocus()); afterStateChange(); });
  document.getElementById('panel').addEventListener('click',e=>{ const bt=e.target.closest('button[data-act]'); if(!bt)return;
    const id=bt.dataset.id, act=bt.dataset.act;
    if(act==='research')research(id); else if(act==='unresearch')unresearch(id); else if(act==='path')researchPathTo(id);
    selId=id; setFocus(activeFocus()); afterStateChange(); });

  // controls
  const cb=(id,key,geom)=>{ const el=document.getElementById(id); el.checked=opt[key];
    el.addEventListener('change',()=>{ opt[key]=el.checked; if(key==='highlight')setFocus(activeFocus()); geom?rebuild():draw(); }); };
  cb('c_fan','fan',true); cb('c_arr','arrows',false); cb('c_disc','discEdges',false); cb('c_hi','highlight',false); cb('c_lane','lane',true); cb('c_icon','icons',false);
  const cp=document.getElementById('c_prog'); cp.checked=opt.progress;
  cp.addEventListener('change',()=>{ opt.progress=cp.checked; afterStateChange(); });
  const sync=()=>{ document.getElementById('c_fan').checked=opt.fan; document.getElementById('c_arr').checked=opt.arrows;
    document.getElementById('c_disc').checked=opt.discEdges; document.getElementById('c_hi').checked=opt.highlight;
    document.getElementById('c_lane').checked=opt.lane; };
  document.getElementById('b_base').addEventListener('click',()=>{ opt.baseline=true; opt.fan=false; opt.discEdges=false; opt.highlight=false; opt.lane=false; focusSet=null; sync(); rebuild(); });
  document.getElementById('b_enh').addEventListener('click',()=>{ opt.baseline=false; opt.fan=true; opt.discEdges=true; opt.highlight=true; sync(); rebuild(); });
  document.getElementById('b_reset').addEventListener('click',()=>{ if(confirm('Reset all research progress?')){ resetProgress(); setFocus(activeFocus()); afterStateChange(); } });
  document.getElementById('b_fit').addEventListener('click',()=>{ fit(); draw(); });
  document.getElementById('zi').addEventListener('click',()=>{ cam.s=Math.min(6,cam.s*1.2); updateZoomLabel(); draw(); });
  document.getElementById('zo').addEventListener('click',()=>{ cam.s=Math.max(.05,cam.s/1.2); updateZoomLabel(); draw(); });
  document.getElementById('q').addEventListener('keydown',e=>{ if(e.key!=='Enter')return;
    const s=e.target.value.trim().toLowerCase(); if(!s)return;
    for(const n of D.nodes){ if(n.id.toLowerCase().includes(s)||n.title.toLowerCase().includes(s)||(n.parts||[]).some(p=>p.name.toLowerCase().includes(s)||(p.title||'').toLowerCase().includes(s))){
      selId=n.id; centerOn(n.id); setFocus(n.id); showPanel(n.id); draw(); break; } }
  });

  window.addEventListener('keydown',e=>{ if(!selId||(e.target&&e.target.tagName==='INPUT')||!opt.progress)return;
    if(e.key==='r'){ const s=stateOf(selId); if(s===RESEARCHABLE)research(selId); else if(s===LOCKED)researchPathTo(selId); afterStateChange(); }
    else if(e.key==='u'){ unresearch(selId); afterStateChange(); } });
  updateHud();
  // console / test API (also lets power users script progress)
  window.RP={ research, unresearch, researchPathTo, resetProgress, stateOf, counts, redraw:afterStateChange, get researched(){return researched;} };
}
document.addEventListener('DOMContentLoaded', init);
