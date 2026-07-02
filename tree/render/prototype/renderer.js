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
const NODE_W = 168, NODE_H = 62, NODE_SQ = 70;   // labelled rect (design view) + square icon tile (~KSP scale 1.0)
const CORNER_R = 15, CORNER_SEGS = 3;   // stock UIGridArea.roundedCornerRadius / lineCornerSegments
const EDGE_W = 2;                        // uniform stroke width (stock lineThickness=2); NEVER varied per state — width change = VectorLine.Draw rebuild
const ARROW = 9;                        // arrowhead size (screen px here; KSP arrow sprite scales with the grid transform)
const GOLD = '#f4d35e', GRAY = '#8a8f98';
const DIM_EDGE = 0.10, DIM_NODE = 0.10; // alpha for de-emphasised (ghosted) elements when a lineage is focused
const FAN_LO = 0.18, FAN_HI = 0.82;     // fraction range along a node side for distributed endpoints

// ---- vec helpers ----
const sub=(a,b)=>[a[0]-b[0],a[1]-b[1]], add=(a,b)=>[a[0]+b[0],a[1]+b[1]], mul=(a,k)=>[a[0]*k,a[1]*k];
const hyp=a=>Math.hypot(a[0],a[1]), norm=a=>{const l=hyp(a)||1;return [a[0]/l,a[1]/l];};

// ---- state ----
let D, byId={}, parents={}, children={}, edges=[];
let cam={s:1,x:0,y:0};                  // world->screen: screenX = worldX*s + x
let hoverId=null, selId=null, focusSet=null, litEdges=null;
let cv, ctx, DPR=window.devicePixelRatio||1;
const opt={ fan:true, arrows:true, discEdges:true, highlight:true, baseline:false, progress:true, routing:'lanes', icons:true, square:true, layout:'sugiyama', spacingX:1.3, spacingY:1.3, diffspread:false, lanePitch:1, halo:false, bundleBeta:0.85 };
const NW=()=>opt.square?NODE_SQ:NODE_W, NH=()=>opt.square?NODE_SQ:NODE_H;   // current tile w/h (rect vs square)
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
  for(const n of D.nodes) n._opos=n.pos;        // keep the compiler layout so we can toggle back to it
  for(const e of edges) e._owp=e.waypoints;
}
function reachable(id, adj){                       // BFS closure (ancestors via parents / descendants via children)
  const seen=new Set(), st=[id];
  while(st.length){ const x=st.pop(); for(const y of adj[x]||[]) if(!seen.has(y)){ seen.add(y); st.push(y); } }
  return seen;
}

// ============================ layout (prototype-owned override) ============================
// Our OWN node placement + edge waypoints, independent of build_tree.py's Sugiyama — so we can move
// nodes and prototype layout in parallel with the compiler/layout agent without touching that file.
// A compact layered layout: tier = column; median/barycentre sweeps to order within a tier (reduce
// crossings); coordinate assignment (rank stack, then neighbour-mean straightening under a min gap);
// per-edge waypoints through each spanned tier. applyLayout() swaps pos+waypoints in/out so ALL the
// downstream code (anchors, routing, lane assignment, fit, hit-test) works unchanged either way.
function layoutSugiyama(){
  const COLW=380*opt.spacingX, SPACING_Y=94*opt.spacingY, med=medianCost();
  const wv=v=>(opt.diffspread && !String(v).startsWith('__d') && byId[v]) ? (0.6+1.4*Math.min(2,(byId[v].cost||0)/med)) : 1;
  // --- layered graph with DUMMY nodes on every >1-tier edge (so long edges join the ordering) ---
  const vtier={}, seed={}, layers={}, prev={}, nxt={}, chains=[];
  for(const n of D.nodes){ vtier[n.id]=n.tier; seed[n.id]=(D.disciplines[n.discipline]||{}).order||99;
    (layers[n.tier]=layers[n.tier]||[]).push(n.id); }
  const addAdj=(a,b)=>{ (nxt[a]=nxt[a]||[]).push(b); (prev[b]=prev[b]||[]).push(a); };
  let dc=0;
  for(const n of D.nodes){ const cid=n.id, ct=n.tier;
    for(const pid of (parents[cid]||[])){ if(!(pid in byId)) continue;
      const pt=byId[pid].tier;
      if(pt>=ct){ addAdj(pid,cid); chains.push([pid,cid,[pid,cid]]); continue; }   // non-forward: straight
      const chain=[pid];
      for(let t=pt+1;t<ct;t++){ const dk='__d'+(dc++); vtier[dk]=t; seed[dk]=seed[pid];
        (layers[t]=layers[t]||[]).push(dk); chain.push(dk); }
      chain.push(cid);
      for(let i=0;i<chain.length-1;i++) addAdj(chain[i],chain[i+1]);
      chains.push([pid,cid,chain]);
    } }
  const order=Object.keys(layers).map(Number).sort((a,b)=>a-b);
  const rank={};
  const reindex=(t,key)=>{ layers[t].sort(key); layers[t].forEach((v,i)=>rank[v]=i); };
  for(const t of order) reindex(t,(a,b)=>(seed[a]-seed[b])||(String(a)<String(b)?-1:1));
  const median=ids=>{ if(!ids||!ids.length) return -1; const vs=ids.map(w=>rank[w]).sort((a,b)=>a-b);
    const m=vs.length>>1; return vs.length%2 ? vs[m] : (vs[m-1]+vs[m])/2; };
  const crossings=()=>{ let c=0;
    for(let oi=0;oi<order.length-1;oi++){ const t=order[oi], es=[];
      for(const u of layers[t]) for(const w of (nxt[u]||[])) if(vtier[w]===t+1) es.push([rank[u],rank[w]]);
      es.sort((a,b)=>a[0]-b[0]||a[1]-b[1]); const seq=es.map(e=>e[1]);
      for(let i=0;i<seq.length;i++) for(let j=i+1;j<seq.length;j++) if(seq[i]>seq[j]) c++; }
    return c; };
  let best=null;                                             // median sweeps; keep least-crossing order
  for(let s=0;s<8;s++){ const asc=s%2===0, adj=asc?prev:nxt, seq=asc?order:order.slice().reverse();
    for(const t of seq){ const keep=Object.assign({},rank);
      reindex(t,(a,b)=>{ const ma=(adj[a]&&adj[a].length)?median(adj[a]):keep[a],
                               mb=(adj[b]&&adj[b].length)?median(adj[b]):keep[b];
                         return (ma-mb)||(keep[a]-keep[b]); }); }
    const c=crossings(); if(best===null||c<best.c){ best={c,ord:{}}; for(const t of order) best.ord[t]=layers[t].slice(); } }
  for(const t of order){ layers[t]=best.ord[t]; layers[t].forEach((v,i)=>rank[v]=i); }
  // --- coordinate assignment: isotonic (PAV) pull toward neighbour mean under a min gap ---
  const isd=v=>String(v).startsWith('__d');
  const gap=(a,b)=>(isd(a)&&isd(b))?0.12:((isd(a)||isd(b))?0.45:1.0*(wv(a)+wv(b))/2);   // dummy thin; real gap grows with cost when diffspread
  const pav=a=>{ const vals=[],cnts=[];
    for(const x of a){ vals.push(x); cnts.push(1);
      while(vals.length>1 && vals[vals.length-2]>=vals[vals.length-1]){
        const v2=vals.pop(),c2=cnts.pop(),v1=vals.pop(),c1=cnts.pop(); vals.push((v1*c1+v2*c2)/(c1+c2)); cnts.push(c1+c2); } }
    const out=[]; for(let i=0;i<vals.length;i++) for(let k=0;k<cnts[i];k++) out.push(vals[i]); return out; };
  const y={}; for(const t of order) for(const v of layers[t]) y[v]=rank[v];
  for(let it=0;it<30;it++){
    const des={}; for(const t of order) for(const v of layers[t]){ const ns=(prev[v]||[]).concat(nxt[v]||[]);
      des[v]= ns.length ? ns.reduce((s,w)=>s+y[w],0)/ns.length : y[v]; }
    for(const t of order){ const row=layers[t]; if(!row.length) continue;
      const c=[0]; let acc=0; for(let i=1;i<row.length;i++){ acc+=gap(row[i-1],row[i]); c[i]=acc; }
      const z=pav(row.map((v,i)=>des[v]-c[i])); for(let i=0;i<row.length;i++) y[row[i]]=z[i]+c[i]; } }
  let miny=Infinity; for(const v in y) if(y[v]<miny) miny=y[v];
  const Y=v=>(y[v]-miny)*SPACING_Y;
  for(const n of D.nodes){ n._lx=n.tier*COLW; n._ly=Y(n.id); }
  const eByKey={}; for(const e of edges) eByKey[e.from+'>'+e.to]=e;   // route each edge through its chain
  for(const [pid,cid,chain] of chains){ const e=eByKey[pid+'>'+cid]; if(e) e._mywp=chain.map(v=>[vtier[v]*COLW, Y(v)]); }
  for(const e of edges) if(!e._mywp) e._mywp=(e.from in byId&&e.to in byId)?[[byId[e.from]._lx,byId[e.from]._ly],[byId[e.to]._lx,byId[e.to]._ly]]:null;
}
function medianCost(){ const cs=D.nodes.map(n=>n.cost||0).filter(c=>c>0).sort((a,b)=>a-b); return cs.length?(cs[cs.length>>1]||1):1; }
function computeLayout(){ if(opt.layout==='bands') layoutBands(); else layoutSugiyama(); }

// Discipline-banded layout: each discipline gets its own horizontal band (ordered by `order`); x=tier,
// nodes stacked within their (discipline,tier) cell. Bands grow with mean cost when diffspread is on.
function layoutBands(){
  const COLW=430*opt.spacingX;   // match the in-game tier width (build_tree TIERW), scaled by X spacing
  const discs=Object.keys(D.disciplines).sort((a,b)=>(D.disciplines[a].order||99)-(D.disciplines[b].order||99));
  const med=medianCost();
  const byDisc={}; for(const n of D.nodes)(byDisc[n.discipline]=byDisc[n.discipline]||[]).push(n);
  const TH=Math.max(NODE_SQ,NODE_H);        // size spacing to the tile so tiles never overlap (either mode)
  const SUBH=TH+26*opt.spacingY, BANDH=TH+96*opt.spacingY;   // scale the GAP, not the tile (Compact stays clear)
  const bandCy={}; let acc=0;
  for(const d of discs){ const ns=byDisc[d]||[]; const perTier={};
    for(const n of ns) perTier[n.tier]=(perTier[n.tier]||0)+1;
    let maxStack=1; for(const k in perTier) if(perTier[k]>maxStack) maxStack=perTier[k];
    let h=Math.max(BANDH, maxStack*SUBH+40*opt.spacingY);
    if(opt.diffspread && ns.length){ const mc=ns.reduce((s,n)=>s+(n.cost||0),0)/ns.length; h*=(0.7+0.9*Math.min(2,mc/med)); }
    bandCy[d]=acc+h/2; acc+=h;
  }
  const cell={}; for(const n of D.nodes){ const k=n.discipline+'|'+n.tier; (cell[k]=cell[k]||[]).push(n); }
  for(const k in cell){ const arr=cell[k]; arr.sort((a,b)=>(a.cost||0)-(b.cost||0)||(a.id<b.id?-1:1));
    arr.forEach((n,i)=>{ n._lx=n.tier*COLW; n._ly=bandCy[n.discipline]+(i-(arr.length-1)/2)*SUBH; }); }
  for(const e of edges){ if(!(e.from in byId)||!(e.to in byId)){ e._mywp=null; continue; }
    const p=byId[e.from], c=byId[e.to], tp=p.tier, tc=c.tier;
    if(tc<=tp){ e._mywp=[[p._lx,p._ly],[c._lx,c._ly]]; continue; }
    const wp=[]; for(let t=tp;t<=tc;t++){ const f=(t-tp)/(tc-tp);
      wp.push([t*COLW, t===tp?p._ly:(t===tc?c._ly:p._ly+(c._ly-p._ly)*f)]); }
    e._mywp=wp; }
}

function applyLayout(){
  const mine = opt.layout!=='compiler';
  for(const n of D.nodes) n.pos = mine ? [n._lx, n._ly] : n._opos;
  for(const e of edges)   e.waypoints = mine ? e._mywp : e._owp;
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
function box(n){ return {x:n.pos[0], y:n.pos[1], w:NW(), h:NH()}; }
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

// round every interior corner of an orthogonal polyline (reuses stock chamfer), clamping the radius
// to the shorter adjacent segment so tight lane jogs don't self-overlap. Keeps it a flat point list.
function roundPolyline(pts, r, segs){
  if(pts.length<3) return pts;
  const out=[pts[0]];
  for(let i=1;i<pts.length-1;i++){
    const a=pts[i-1], v=pts[i], b=pts[i+1];
    const rr=Math.min(r, 0.45*Math.min(hyp(sub(a,v)), hyp(sub(b,v))));
    if(rr<0.5){ out.push(v); continue; }
    for(const p of chamfer(a,v,b,rr,segs)) out.push(p);
  }
  out.push(pts[pts.length-1]);
  return out;
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

// ============================ routing VARIANTS ============================
// Line/edge-routing styles to compare (opt.routing). Each returns ONE flat polyline in world space
// (spline is tessellated to points so the KSP Vectrosity port stays a single VectorLine per edge).
// All consume the layout's dummy chain (e.waypoints) where relevant + the fan slots (_tF/_tT).
//   lanes      orthogonal, vertical legs packed into per-gutter lanes (buildLaneRoutes → e.laneGeom)
//   ortho-mid  stock KSP elbow: one riser at mid-X (routeEdge), ignores intermediate tiers
//   ortho-late orthogonal elbow with the riser near the TARGET (converging "into node" look)
//   polyline   straight segments through the dummy waypoints (classic Sugiyama)
//   spline     smooth Catmull-Rom curve through the dummy waypoints (dagre/d3 look)
//   bezier     horizontal-tangent cubic Bézier, endpoint-based (React-Flow "bumpX"; clean modern flow)
//   bundle     edge bundling — pull to per-node out/in hubs by β, declutters dense fan-in/out
//   octilinear metro/subway routing — horizontal, one 45° diagonal, horizontal into the target
//   direct     one straight line source→target (baseline; ignores dummies)
function pathThroughDummies(e){          // source-right anchor, centred interior dummies, target-left anchor
  const wp=e.waypoints; if(!wp||wp.length<2) return null;
  const pts=[anchor(byId[e.from],'RIGHT',e._tF)];
  for(let i=1;i<wp.length-1;i++) pts.push([wp[i][0], wp[i][1]+0.5*NH()]);
  pts.push(anchor(byId[e.to],'LEFT',e._tT));
  return pts;
}
function catmullRom(P, seg){             // Catmull-Rom through P → sampled flat polyline
  if(!P||P.length<3) return P;
  const out=[P[0]];
  for(let i=0;i<P.length-1;i++){
    const p0=P[i-1]||P[i], p1=P[i], p2=P[i+1], p3=P[i+2]||P[i+1];
    for(let s=1;s<=seg;s++){ const t=s/seg, t2=t*t, t3=t2*t;
      out.push([
        0.5*((2*p1[0])+(-p0[0]+p2[0])*t+(2*p0[0]-5*p1[0]+4*p2[0]-p3[0])*t2+(-p0[0]+3*p1[0]-3*p2[0]+p3[0])*t3),
        0.5*((2*p1[1])+(-p0[1]+p2[1])*t+(2*p0[1]-5*p1[1]+4*p2[1]-p3[1])*t2+(-p0[1]+3*p1[1]-3*p2[1]+p3[1])*t3)]);
    }
  }
  return out;
}
function routeOrthoLate(e){              // orthogonal elbow, single riser near the TARGET
  const p=anchor(byId[e.from],'RIGHT',e._tF), c=anchor(byId[e.to],'LEFT',e._tT);
  if(Math.abs(p[1]-c[1])<0.5) return [p,c];
  const rx=c[0]-Math.max(18,Math.min(60,(c[0]-p[0])*0.3));   // riser just left of the target node
  const k1=[rx,p[1]], k2=[rx,c[1]];
  return [p, ...chamfer(p,k1,k2,CORNER_R,CORNER_SEGS), ...chamfer(k1,k2,c,CORNER_R,CORNER_SEGS), c];
}

// ---- NEW variants (2026-07-02) ----
// cubic Bézier P0..P3 → sampled flat polyline (tessellated so the KSP Vectrosity port stays ONE line).
function cubicBezier(p0,p1,p2,p3,segs){
  const out=[];
  for(let i=0;i<=segs;i++){ const t=i/segs, u=1-t, a=u*u*u, b=3*u*u*t, cc=3*u*t*t, d=t*t*t;
    out.push([a*p0[0]+b*p1[0]+cc*p2[0]+d*p3[0], a*p0[1]+b*p1[1]+cc*p2[1]+d*p3[1]]); }
  return out;
}
// bezier: horizontal-tangent cubic (React-Flow "bumpX" / dagre look). LEAVES the source rightward and
// ARRIVES at the target leftward — the tangents are flat so it reads as a clean left→right flow. Unlike
// `spline` (which interpolates the dummy chain and can wiggle), this is a single predictable S with no
// mid-points, so it never strays across a column on its own. Endpoint-based (ignores dummies by design).
const BEZ_K=0.5;                         // control-point reach as a fraction of the horizontal span
function routeBezier(e){
  const p=anchor(byId[e.from],'RIGHT',e._tF), c=anchor(byId[e.to],'LEFT',e._tT);
  if(c[0]<=p[0]+2) return routeEdge(e);   // back/same-tier edge: a horizontal-tangent bezier would loop
  if(Math.abs(p[1]-c[1])<0.5) return [p,c];
  const dx=c[0]-p[0];
  return cubicBezier(p, [p[0]+BEZ_K*dx,p[1]], [c[0]-BEZ_K*dx,c[1]], c, 18);
}
// bundle: hierarchical edge bundling. Every edge leaving a node is pulled toward that node's OUT-hub
// (the mean y of its targets) and every edge entering a node toward its IN-hub (mean y of its sources),
// by strength β (opt.bundleBeta). Edges to nearby targets thus share a curved trunk and only peel off
// near their ends — the dense root fan-out / Systems-Integration block collapse into a few legible
// bundles instead of a hairball. β=0 ≡ `bezier`; β=1 ≡ fully merged. Still one tessellated line per edge.
let bundleOutY={}, bundleInY={};
function buildBundleHubs(){
  const outYs={}, inYs={};
  for(const e of edges){ if(!(e.from in byId)||!(e.to in byId)) continue;
    const s=anchor(byId[e.from],'RIGHT',e._tF), t=anchor(byId[e.to],'LEFT',e._tT);
    (outYs[e.from]=outYs[e.from]||[]).push(t[1]); (inYs[e.to]=inYs[e.to]||[]).push(s[1]); }
  const mean=a=>a.reduce((x,y)=>x+y,0)/a.length;
  bundleOutY={}; bundleInY={};
  for(const id in outYs) bundleOutY[id]=mean(outYs[id]);
  for(const id in inYs)  bundleInY[id]=mean(inYs[id]);
}
function routeBundle(e){
  const p=anchor(byId[e.from],'RIGHT',e._tF), c=anchor(byId[e.to],'LEFT',e._tT);
  if(c[0]<=p[0]+2) return routeEdge(e);
  const dx=c[0]-p[0], b=opt.bundleBeta;
  const hOut=bundleOutY[e.from], hIn=bundleInY[e.to];
  const c1y=p[1]+((hOut==null?p[1]:hOut)-p[1])*b, c2y=c[1]+((hIn==null?c[1]:hIn)-c[1])*b;
  return cubicBezier(p, [p[0]+BEZ_K*dx,c1y], [c[0]-BEZ_K*dx,c2y], c, 20);
}
// octilinear: metro/subway-map routing — horizontal run, one 45° diagonal to change rows, horizontal
// into the target. Distinct clean aesthetic; corners rounded via the stock chamfer. Falls back to the
// converging orthogonal elbow when the span is too short to fit a 45° leg.
function routeOctilinear(e){
  const p=anchor(byId[e.from],'RIGHT',e._tF), c=anchor(byId[e.to],'LEFT',e._tT);
  const dx=c[0]-p[0], dy=c[1]-p[1], ady=Math.abs(dy);
  if(ady<0.5) return [p,c];
  if(dx<=ady+8) return routeOrthoLate(e);            // no room for a 45° leg → converging elbow
  const run=Math.max(12,(dx-ady)/2);
  const k1=[p[0]+run, p[1]], k2=[p[0]+run+ady, c[1]];
  return roundPolyline([p,k1,k2,c], CORNER_R, CORNER_SEGS);
}
function edgeGeom(e){
  switch(opt.routing){
    case 'ortho-mid':   return routeEdge(e);
    case 'ortho-late':  return routeOrthoLate(e);
    case 'polyline':    return pathThroughDummies(e) || routeEdge(e);
    case 'spline':      return catmullRom(pathThroughDummies(e), 14) || routeEdge(e);
    case 'bezier':      return routeBezier(e);
    case 'bundle':      return routeBundle(e);
    case 'octilinear':  return routeOctilinear(e);
    case 'direct':      return [anchor(byId[e.from],'RIGHT',e._tF), anchor(byId[e.to],'LEFT',e._tT)];
    case 'lanes':
    default:            return e.laneGeom || routeEdge(e);
  }
}

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
    // endpoints use the fan slot (spread along the node side); interior dummies stay centred
    const ts=e.waypoints.map(p=>tierOf(p[0]));
    const ys=e.waypoints.map((p,i)=>p[1]+(i===0?e._tF:(i===e.waypoints.length-1?e._tT:0.5))*NH());
    chains.push([e,ts,ys]);
    for(let i=0;i<ts.length-1;i++)
      (seg[ts[i]]=seg[ts[i]]||[]).push([Math.min(ys[i],ys[i+1]),Math.max(ys[i],ys[i+1]),e.from+'>'+e.to+'#'+i]);
  }
  const lane={}, lanesN={};
  for(const g in seg){ const s=seg[g].sort((a,b)=>a[0]-b[0]), ends=[];
    for(const [lo,hi,key] of s){ let l=ends.findIndex(h=>h<=lo+1e-6); if(l<0){ l=ends.length; ends.push(hi); } else ends[l]=hi; lane[key]=l; }
    lanesN[g]=ends.length; }
  // LANE-ORDER: reassign each gutter's lane x-slots by leg barycentre so tracks run monotonically
  // top->bottom — the horizontal connectors then cross far less than first-fit order.
  const laneRank={};
  for(const g in seg){
    const sum=[], cnt=[];
    for(const [lo,hi,key] of seg[g]){ const l=lane[key]; sum[l]=(sum[l]||0)+(lo+hi)/2; cnt[l]=(cnt[l]||0)+1; }
    const order=[...Array(lanesN[g]).keys()].sort((a,b)=>(sum[a]/cnt[a])-(sum[b]/cnt[b]));
    const m={}; order.forEach((oldL,newL)=>m[oldL]=newL); laneRank[g]=m;
  }
  // tight, fixed pitch between lanes (centred in the gutter), not spread across the whole gutter;
  // clamps down only if a very busy gutter would otherwise overflow ~80% of its width.
  const LANE_PITCH=opt.lanePitch;   // px between parallel lanes (live-tunable in the bar)
  const laneX=(g,l)=>{ const n=lanesN[g], gw=TW-NW(), pitch=Math.min(LANE_PITCH,(gw*0.8)/Math.max(1,n)), cx=tierX(g)+NW()+gw/2;
    return cx+(l-(n-1)/2)*pitch; };
  const built=[];
  for(const [e,ts,ys] of chains){
    const pts=[[tierX(ts[0])+NW(), ys[0]]];
    for(let i=0;i<ts.length-1;i++){ const g=ts[i]; const lx=laneX(g, laneRank[g][lane[e.from+'>'+e.to+'#'+i]]); pts.push([lx,ys[i]],[lx,ys[i+1]]); }
    pts.push([tierX(ts[ts.length-1]), ys[ys.length-1]]);
    built.push(pts);
    e.laneGeom=pts;   // rounded below, after horizontal-track separation
  }
  // HORIZONTAL TRACKS: interior horizontal runs that overlap on the same row get bumped to separate
  // tracks (offset y on BOTH endpoints; the adjoining vertical legs just change length, so the path
  // stays orthogonal + continuous). Skip the first/last segment (node-touching — handled by the fan).
  const rows={};
  for(const pts of built)
    for(let i=1;i<pts.length-2;i++)
      if(Math.abs(pts[i][1]-pts[i+1][1])<0.5 && Math.abs(pts[i][0]-pts[i+1][0])>0.5){
        const y=Math.round(pts[i][1]); (rows[y]=rows[y]||[]).push([Math.min(pts[i][0],pts[i+1][0]), Math.max(pts[i][0],pts[i+1][0]), pts, i]);
      }
  const HGAP=6;
  for(const y in rows){ const ends=[];
    for(const s of rows[y].sort((a,b)=>a[0]-b[0])){
      let tk=ends.findIndex(x=>x<=s[0]+1e-6); if(tk<0){ tk=ends.length; ends.push(s[1]); } else ends[tk]=s[1];
      if(tk>0){ const off=tk*HGAP; s[2][s[3]][1]+=off; s[2][s[3]+1][1]+=off; }
    } }
  for(const [e] of chains) e.laneGeom=roundPolyline(e.laneGeom, CORNER_R, CORNER_SEGS);   // smooth the jogs
}

function buildGeometry(){
  computeSlots();
  if(opt.routing==='lanes') buildLaneRoutes();        // only 'lanes' needs the gutter lane-packing pass
  else if(opt.routing==='bundle') buildBundleHubs();  // bundle needs per-node out/in hub y's first
  for(const e of edges){
    if(!(e.from in byId)||!(e.to in byId)){ e.geom=null; continue; }
    e.geom = edgeGeom(e);   // routing variant (opt.routing)
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

  // tier column labels (orientation) — on the BOTTOM edge; the top is covered by the toolbar
  ctx.fillStyle='#5a6673'; ctx.font='600 12px Segoe UI,Helvetica,Arial'; ctx.textAlign='left'; ctx.textBaseline='bottom';
  const tierX={}; for(const n of D.nodes){ if(!(n.tier in tierX)) tierX[n.tier]=n.pos[0]; }
  const tierLabelY=cv.clientHeight-30;   // clear of the #foot / #hud bars pinned at bottom:8px
  for(const t in tierX){ ctx.fillText('T'+t, SX(tierX[t]), tierLabelY); }

  // edges (under nodes)
  for(const e of edges){
    if(!e.geom) continue;
    const lit = !focusing || (litEdges && litEdges.has(e));
    const parentDone = researched.has(e.from);
    let color;
    if(focusing && lit)                                                              // focused path: full discipline
      color = e.anyToUnlock ? GOLD : ((opt.discEdges && !opt.baseline) ? e.discColor : GRAY);   // colour so it pops
    else if(opt.progress && !parentDone) color = e.anyToUnlock ? GOLD_DIM : EDGE_LOCK;   // prereq not researched (stock gray)
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

// desaturate a hex colour toward its own grey (amt 0..1) — used to "grey out" locked nodes.
function desat(hex, amt){
  const c=(hex||'').replace('#',''); if(c.length<6) return hex;
  const r=parseInt(c.slice(0,2),16), g=parseInt(c.slice(2,4),16), b=parseInt(c.slice(4,6),16);
  const l=0.3*r+0.59*g+0.11*b, m=v=>Math.round(v+(l-v)*amt);
  return `rgb(${m(r)},${m(g)},${m(b)})`;
}

function drawNode(n, focusing){
  const b=box(n), x=SX(b.x), y=SY(b.y), w=b.w*cam.s, h=b.h*cam.s;
  const disc=D.disciplines[n.discipline]||{color:'#888',title:n.discipline};
  const st = opt.progress ? stateOf(n.id) : null;
  const inFocus = focusing && focusSet.has(n.id);       // on the highlighted lineage
  const dimFocus = focusing && !inFocus;                // off it -> ghost (DIM_NODE)
  // 3-state read (portable: tint + alpha + badge). LOCKED = desaturated + dim; RESEARCHABLE = glow ring;
  // RESEARCHED = ✓ badge. But a LOCKED node ON the focused lineage pops at full colour (not desaturated).
  const lockedRest = opt.progress && st===LOCKED && !inFocus;
  const alpha = dimFocus ? DIM_NODE : (lockedRest ? 0.42 : 1);
  const fill = lockedRest ? desat(disc.color, 0.8) : disc.color;
  ctx.globalAlpha = alpha;

  roundRect(x,y,w,h,Math.max(2,3*cam.s)); ctx.fillStyle=fill; ctx.fill();

  if(opt.progress && !dimFocus){
    if(st===RESEARCHABLE){                         // AVAILABLE: bright glow ring — the actionable frontier
      ctx.save(); ctx.shadowColor=C_AVAIL; ctx.shadowBlur=Math.max(4,9*cam.s);
      ctx.strokeStyle=C_AVAIL; ctx.lineWidth=Math.max(2,3*cam.s); ctx.stroke(); ctx.restore();
    } else if(st===RESEARCHED){                     // DONE: subtle green ring (+ ✓ badge below)
      ctx.strokeStyle=C_DONE; ctx.lineWidth=2; ctx.stroke();
    }
  }
  if(focusing && opt.halo && inFocus && n.id!==selId){   // HALO: white outline pops the lineage over the ghost
    ctx.globalAlpha=1; ctx.strokeStyle='#fff'; ctx.lineWidth=Math.max(1.5,2.4*cam.s); ctx.stroke();
  }
  if(n.id===selId){ ctx.strokeStyle='#fff'; ctx.lineWidth=3; ctx.stroke(); }
  else if(n.id===hoverId){ ctx.strokeStyle='rgba(255,255,255,.85)'; ctx.lineWidth=2; ctx.stroke(); }

  const ink = lum(disc.color)>140 ? '#10181f' : '#f3f3f3';   // contrast text (fixes dark-on-dark)
  if(opt.square){                                   // KSP-faithful: square tile = icon only, name on hover/panel
    if(opt.icons && iconReady(disc.icon)){ const s=Math.min(w,h)*0.82; ctx.globalAlpha=alpha;
      ctx.drawImage(iconImg[disc.icon], x+(w-s)/2, y+(h-s)/2, s, s); }
    else if(cam.s>0.25){ ctx.globalAlpha=alpha; ctx.fillStyle=ink; ctx.textAlign='center'; ctx.textBaseline='middle';
      ctx.font=`600 ${Math.max(7,9*cam.s)}px Segoe UI,Helvetica,Arial`; ctx.fillText(clip(n.title,w*0.86), x+w/2, y+h/2); }
  } else {                                          // design view: corner icon + wrapped title + badge
    if(opt.icons && iconReady(disc.icon) && cam.s>0.15){ const s=Math.min(w,h)*0.4; ctx.globalAlpha=alpha;
      ctx.drawImage(iconImg[disc.icon], x+3*cam.s, y+3*cam.s, s, s); }
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
  }
  if(opt.progress && !dimFocus && st===RESEARCHED && cam.s>0.18){    // ✓ researched badge: green disc + tick
    const r=Math.max(4.5,6.5*cam.s), cx=x+w-r-1.5, cy=y+r+1.5;
    ctx.globalAlpha=alpha; ctx.fillStyle=C_DONE; ctx.beginPath(); ctx.arc(cx,cy,r,0,6.2832); ctx.fill();
    ctx.strokeStyle='#08140a'; ctx.lineWidth=Math.max(1.2,1.6*cam.s); ctx.lineCap='round'; ctx.lineJoin='round';
    ctx.beginPath(); ctx.moveTo(cx-r*0.42,cy+r*0.04); ctx.lineTo(cx-r*0.08,cy+r*0.4); ctx.lineTo(cx+r*0.48,cy-r*0.4); ctx.stroke();
  }
  if(opt.square && n.id===hoverId){                 // square tiles have no in-tile name -> label on hover
    ctx.globalAlpha=1; ctx.fillStyle='#fff'; ctx.textAlign='center'; ctx.textBaseline='top';
    ctx.font=`600 ${Math.max(9,11*cam.s)}px Segoe UI,Helvetica,Arial`; ctx.fillText(clip(n.title,220), x+w/2, y+h+3*cam.s);
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
  const x0=Math.min(...xs), x1=Math.max(...xs)+NW(), y0=Math.min(...ys), y1=Math.max(...ys)+NH();
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
  if(new URLSearchParams(location.search).get('routing')) opt.routing=new URLSearchParams(location.search).get('routing');
  if(new URLSearchParams(location.search).has('square')) opt.square=true;
  const P0=new URLSearchParams(location.search);
  if(P0.get('layout')) opt.layout=P0.get('layout'); else if(P0.has('mylayout')) opt.layout='sugiyama';
  if(P0.get('spacingx')) opt.spacingX=+P0.get('spacingx')||opt.spacingX;
  if(P0.get('spacingy')) opt.spacingY=+P0.get('spacingy')||opt.spacingY;
  const sp0=P0.get('spacing');                     // legacy coarse preset → drive both axes
  if(sp0==='compact') opt.spacingX=opt.spacingY=0.7; else if(sp0==='airy') opt.spacingX=opt.spacingY=1.6; else if(sp0==='normal') opt.spacingX=opt.spacingY=1;
  if(P0.has('diffspread')) opt.diffspread=true;
  if(P0.get('lanePitch')) opt.lanePitch=+P0.get('lanePitch')||opt.lanePitch;
  if(P0.get('bundle')!=null) opt.bundleBeta=Math.max(0,Math.min(1,+P0.get('bundle')||opt.bundleBeta));
  buildModel(); restore();
  const rq=new URLSearchParams(location.search).get('research');   // ?research=id,id — shareable snapshot / demo
  if(rq) rq.split(',').forEach(x=>{ if(byId[x]) researched.add(x); });
  if(opt.layout!=='compiler') computeLayout(); applyLayout();
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
  cb('c_fan','fan',true); cb('c_arr','arrows',false); cb('c_disc','discEdges',false); cb('c_hi','highlight',false); cb('c_icon','icons',false); cb('c_square','square',true); cb('c_halo','halo',false);
  const selR=document.getElementById('s_route'); selR.value=opt.routing;
  selR.addEventListener('change',()=>{ opt.routing=selR.value; rebuild(); });
  const cp=document.getElementById('c_prog'); cp.checked=opt.progress;
  cp.addEventListener('change',()=>{ opt.progress=cp.checked; afterStateChange(); });
  const relayout=()=>{ if(opt.layout!=='compiler') computeLayout(); applyLayout(); buildGeometry(); fit(); draw(); };
  const selL=document.getElementById('s_layout'); selL.value=opt.layout;
  selL.addEventListener('change',()=>{ opt.layout=selL.value; relayout(); });
  const wireSp=(id,vid,key)=>{ const r=document.getElementById(id), v=document.getElementById(vid);
    r.value=opt[key]; v.textContent=opt[key].toFixed(1)+'×';
    r.addEventListener('input',()=>{ opt[key]=+r.value; v.textContent=opt[key].toFixed(1)+'×'; relayout(); }); };
  wireSp('r_spx','r_spx_v','spacingX'); wireSp('r_spy','r_spy_v','spacingY');
  const cd=document.getElementById('c_diff'); cd.checked=opt.diffspread;
  cd.addEventListener('change',()=>{ opt.diffspread=cd.checked; relayout(); });
  const rl=document.getElementById('r_lane'), rlv=document.getElementById('r_lane_v');
  rl.value=opt.lanePitch; rlv.textContent=opt.lanePitch+'px';
  rl.addEventListener('input',()=>{ opt.lanePitch=+rl.value; rlv.textContent=opt.lanePitch+'px'; if(opt.routing==='lanes')rebuild(); });
  const rb=document.getElementById('r_bundle'), rbv=document.getElementById('r_bundle_v');
  rb.value=opt.bundleBeta; rbv.textContent=opt.bundleBeta.toFixed(2);
  rb.addEventListener('input',()=>{ opt.bundleBeta=+rb.value; rbv.textContent=opt.bundleBeta.toFixed(2); if(opt.routing==='bundle')rebuild(); });
  const sync=()=>{ document.getElementById('c_fan').checked=opt.fan; document.getElementById('c_arr').checked=opt.arrows;
    document.getElementById('c_disc').checked=opt.discEdges; document.getElementById('c_hi').checked=opt.highlight;
    document.getElementById('s_route').value=opt.routing; };
  document.getElementById('b_base').addEventListener('click',()=>{ opt.baseline=true; opt.fan=false; opt.discEdges=false; opt.highlight=false; opt.routing='ortho-mid'; focusSet=null; sync(); rebuild(); });
  document.getElementById('b_enh').addEventListener('click',()=>{ opt.baseline=false; opt.fan=true; opt.discEdges=true; opt.highlight=true; opt.routing='lanes'; sync(); rebuild(); });
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
