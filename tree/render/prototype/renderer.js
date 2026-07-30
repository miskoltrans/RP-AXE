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
const DIM_DONE = 0.45;                  // ghosted RESEARCHED nodes ride higher: green = done must survive the focus dim
const FAN_LO = 0.18, FAN_HI = 0.82;     // fraction range along a node side for distributed endpoints

// ---- vec helpers ----
const sub=(a,b)=>[a[0]-b[0],a[1]-b[1]], add=(a,b)=>[a[0]+b[0],a[1]+b[1]], mul=(a,k)=>[a[0]*k,a[1]*k];
const hyp=a=>Math.hypot(a[0],a[1]), norm=a=>{const l=hyp(a)||1;return [a[0]/l,a[1]/l];};

// ---- state ----
let D, byId={}, parents={}, children={}, edges=[];
let cam={s:1,x:0,y:0};                  // world->screen: screenX = worldX*s + x
let hoverId=null, selId=null, focusSet=null, litEdges=null;
let cv, ctx, DPR=window.devicePixelRatio||1;
// Fixed rendering flags (no longer toggleable — always these values): arrowheads/icons/discipline
// colours/lineage-highlight/research-state/fan-endpoints/square-tiles ON, halo OFF, baseline OFF.
const opt={ fan:true, xfan:true, xfanPitch:16, avoid:true, arrows:true, discEdges:true, highlight:true, baseline:false, progress:true, routing:'junction', icons:true, square:true, layout:'compiler', spacingX:1.0, spacingY:1.0, diffspread:false, halo:false, doneStyle:'stamp' };   // doneStyle: 'stamp' (keep disc colour + bold green ring/check) | 'tile' (recolour tile green) — toggle with the 'd' key
const NW=()=>opt.square?NODE_SQ:NODE_W, NH=()=>opt.square?NODE_SQ:NODE_H;   // current tile w/h (rect vs square)
let researched=new Set();                      // research state (KSP RDNode.State: researched/researchable/locked)
const LSKEY='rpaxe-tree-progress';
const C_DONE='#4ade80', C_AVAIL='#38bdf8';     // researched / researchable (the frontier = "what to research next")
const C_DONE_FILL='#2fa25f';                    // doneStyle='tile': the green a researched tile is recoloured to
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
// Layered layout, parameterized (cfg defaults to the original behaviour so 'sugiyama' is unchanged):
//   cfg.coords 'pav' (default) isotonic neighbour-mean | 'bk' Brandes–Köpf block alignment (straight edges)
//   cfg.order  undefined crossing-min only | 'disc' discipline-constrained ordering (soft swim-lanes)
function layoutSugiyama(cfg){
  cfg=cfg||{}; const useBK=cfg.coords==='bk', discOrd=cfg.order==='disc';
  const COLW=380*opt.spacingX, SPACING_Y=94*opt.spacingY, med=medianCost();
  const wv=v=>(opt.diffspread && !String(v).startsWith('__d') && byId[v]) ? (0.6+1.4*Math.min(2,(byId[v].cost||0)/med)) : 1;
  // --- layered graph with DUMMY nodes on every >1-tier edge. segPrev/segNext = adjacent-rank segments
  //     ONLY (the "proper layering" Brandes–Köpf needs); prev/nxt keep every edge for ordering/PAV. ---
  const vtier={}, seed={}, layers={}, prev={}, nxt={}, segPrev={}, segNext={}, chains=[];
  for(const n of D.nodes){ vtier[n.id]=n.tier; seed[n.id]=(D.disciplines[n.discipline]||{}).order||99;
    (layers[n.tier]=layers[n.tier]||[]).push(n.id); }
  const addAdj=(a,b)=>{ (nxt[a]=nxt[a]||[]).push(b); (prev[b]=prev[b]||[]).push(a); };
  const addSeg=(a,b)=>{ (segNext[a]=segNext[a]||[]).push(b); (segPrev[b]=segPrev[b]||[]).push(a); };
  let dc=0;
  for(const n of D.nodes){ const cid=n.id, ct=n.tier;
    for(const pid of (parents[cid]||[])){ if(!(pid in byId)) continue;
      const pt=byId[pid].tier;
      if(pt>=ct){ addAdj(pid,cid); chains.push([pid,cid,[pid,cid]]); continue; }   // non-forward: no BK segment
      const chain=[pid];
      for(let t=pt+1;t<ct;t++){ const dk='__d'+(dc++); vtier[dk]=t; seed[dk]=seed[pid];
        (layers[t]=layers[t]||[]).push(dk); chain.push(dk); }
      chain.push(cid);
      for(let i=0;i<chain.length-1;i++){ addAdj(chain[i],chain[i+1]); addSeg(chain[i],chain[i+1]); }
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
                         if(discOrd){ const sc=seed[a]-seed[b]; if(sc) return sc; }   // disciplines contiguous first
                         return (ma-mb)||(keep[a]-keep[b]); }); }
    const c=crossings(); if(best===null||c<best.c){ best={c,ord:{}}; for(const t of order) best.ord[t]=layers[t].slice(); } }
  for(const t of order){ layers[t]=best.ord[t]; layers[t].forEach((v,i)=>rank[v]=i); }
  // --- coordinate assignment ---
  const isd=v=>String(v).startsWith('__d');
  const gap=(a,b)=>{                              // min separation between two vertices stacked in a layer
    if(isd(a)&&isd(b)) return 0.12;               // dummy–dummy: thin (long edges pack tight)
    if(isd(a)||isd(b)) return 0.45;
    if(discOrd){ const da=(byId[a]||{}).discipline, db=(byId[b]||{}).discipline; if(da&&db&&da!==db) return 1.5; }  // band gutter
    return 1.0*(wv(a)+wv(b))/2;                   // real–real: grows with cost when diffspread
  };
  let y;
  if(useBK){
    y=bkCoords(order, layers, segPrev, gap, isd);   // Brandes–Köpf: aligns nodes into blocks ⇒ straight edges
  } else {                                          // isotonic (PAV) pull toward neighbour mean under min gap
    const pav=a=>{ const vals=[],cnts=[];
      for(const x of a){ vals.push(x); cnts.push(1);
        while(vals.length>1 && vals[vals.length-2]>=vals[vals.length-1]){
          const v2=vals.pop(),c2=cnts.pop(),v1=vals.pop(),c1=cnts.pop(); vals.push((v1*c1+v2*c2)/(c1+c2)); cnts.push(c1+c2); } }
      const out=[]; for(let i=0;i<vals.length;i++) for(let k=0;k<cnts[i];k++) out.push(vals[i]); return out; };
    y={}; for(const t of order) for(const v of layers[t]) y[v]=rank[v];
    for(let it=0;it<30;it++){
      const des={}; for(const t of order) for(const v of layers[t]){ const ns=(prev[v]||[]).concat(nxt[v]||[]);
        des[v]= ns.length ? ns.reduce((s,w)=>s+y[w],0)/ns.length : y[v]; }
      for(const t of order){ const row=layers[t]; if(!row.length) continue;
        const c=[0]; let acc=0; for(let i=1;i<row.length;i++){ acc+=gap(row[i-1],row[i]); c[i]=acc; }
        const z=pav(row.map((v,i)=>des[v]-c[i])); for(let i=0;i<row.length;i++) y[row[i]]=z[i]+c[i]; } }
  }
  let miny=Infinity; for(const v in y) if(y[v]<miny) miny=y[v];
  const Y=v=>(y[v]-miny)*SPACING_Y;
  for(const n of D.nodes){ n._lx=n.tier*COLW; n._ly=Y(n.id); }
  const eByKey={}; for(const e of edges) eByKey[e.from+'>'+e.to]=e;   // route each edge through its chain
  for(const [pid,cid,chain] of chains){ const e=eByKey[pid+'>'+cid]; if(e) e._mywp=chain.map(v=>[vtier[v]*COLW, Y(v)]); }
  for(const e of edges) if(!e._mywp) e._mywp=(e.from in byId&&e.to in byId)?[[byId[e.from]._lx,byId[e.from]._ly],[byId[e.to]._lx,byId[e.to]._ly]]:null;
}

// ---- Brandes–Köpf horizontal (here vertical) coordinate assignment ----
// "Fast and Simple Horizontal Coordinate Assignment" (Brandes & Köpf 2002). Aligns each vertex to its
// median neighbour into vertical BLOCKS, then compacts blocks under a min-gap — so aligned edges become
// dead-straight runs (long edges through dummy chains especially). This is what makes dagre/ELK look
// crisp under orthogonal routing vs. a neighbour-mean pass, which smears edges into gentle diagonals.
// We run two directions (down-left + down-right via a within-layer mirror) and average to balance the
// left/right bias — not the full 4-way balance, but the visible asymmetry for an L→R tree is L/R. A final
// monotone per-layer sweep guarantees separation (averaging two valid runs can nudge nodes together).
function bkType1(L, predOf, ord, isd){        // mark segments that cross an inner (dummy–dummy) segment
  const conf=new Set();
  for(let k=0;k<L.length-1;k++){ const upper=L[k], lower=L[k+1]; let k0=0, scan=0;
    for(let l1=0;l1<lower.length;l1++){ const v=lower[l1];
      let innerPos=-1; if(isd(v)) for(const u of (predOf[v]||[])) if(isd(u)&&ord[u]>innerPos) innerPos=ord[u];
      if(l1===lower.length-1 || innerPos>=0){ const k1=innerPos>=0?innerPos:upper.length-1;
        for(; scan<=l1; scan++){ const w=lower[scan];
          for(const u of (predOf[w]||[])) if((ord[u]<k0||ord[u]>k1) && !(isd(u)&&isd(w))) conf.add(u+' '+w); }
        k0=k1;
      } } }
  return conf;
}
function bkAlign(L, predOf, ord, conf){       // vertical alignment → {root, align} blocks (down, median)
  const root={}, align={};
  for(const layer of L) for(const v of layer){ root[v]=v; align[v]=v; }
  const has=(u,w)=>conf.has(u+' '+w)||conf.has(w+' '+u);
  for(const layer of L){ let r=-1;
    for(const v of layer){ const ws=predOf[v]; if(!ws||!ws.length) continue;
      const mp=(ws.length-1)/2;
      for(let i=Math.floor(mp); i<=Math.ceil(mp); i++){ if(align[v]!==v) break;
        const w=ws[i]; if(r<ord[w] && !has(w,v)){ align[w]=v; root[v]=root[w]; align[v]=root[w]; r=ord[w]; } }
    } }
  return {root,align};
}
function bkCompact(L, root, align, sep){       // horizontal compaction → coord per vertex (one direction)
  const above={}; for(const layer of L) for(let i=0;i<layer.length;i++) above[layer[i]]=i>0?layer[i-1]:null;
  const X={}, sink={}, shift={};
  for(const layer of L) for(const v of layer){ sink[v]=v; shift[v]=Infinity; }
  function place(v){ if(v in X) return; X[v]=0; let w=v;
    do{ const u=above[w];
      if(u!=null){ const ru=root[u]; place(ru);
        if(sink[v]===v) sink[v]=sink[ru];
        const d=sep(u,w);
        if(sink[v]===sink[ru]) X[v]=Math.max(X[v], X[ru]+d);
        else shift[sink[ru]]=Math.min(shift[sink[ru]], X[v]-X[ru]-d);
      } w=align[w];
    } while(w!==v);
  }
  for(const layer of L) for(const v of layer) if(root[v]===v) place(v);
  const xs={}; for(const layer of L) for(const v of layer){ xs[v]=X[root[v]];
    const s=shift[sink[root[v]]]; if(s<Infinity) xs[v]+=s; }
  return xs;
}
function bkRun(L, segPrev, sep, isd){          // one BK pass over ordered layers L (predecessors = upper layer)
  const ord={}; for(const layer of L) layer.forEach((v,i)=>ord[v]=i);
  const predOf={}; for(const layer of L) for(const v of layer)
    predOf[v]=(segPrev[v]||[]).slice().sort((a,b)=>ord[a]-ord[b]);
  const conf=bkType1(L,predOf,ord,isd);
  const {root,align}=bkAlign(L,predOf,ord,conf);
  return bkCompact(L,root,align,sep);
}
function bkCoords(order, layers, segPrev, sep, isd){
  const L=order.map(t=>layers[t]);
  const cL=bkRun(L, segPrev, sep, isd);                 // down-left
  const cRr=bkRun(L.map(l=>l.slice().reverse()), segPrev, sep, isd);   // down-right (within-layer mirror)
  const cR={}; for(const k in cRr) cR[k]=-cRr[k];       // …measured from the far side ⇒ negate to shared frame
  const norm=m=>{ let mn=Infinity; for(const k in m) if(m[k]<mn) mn=m[k]; for(const k in m) m[k]-=mn; };
  norm(cL); norm(cR);
  const y={}; for(const layer of L) for(const v of layer) y[v]=(cL[v]+cR[v])/2;   // balance L/R bias
  for(const layer of L) for(let i=1;i<layer.length;i++){                          // guarantee separation
    const need=y[layer[i-1]]+sep(layer[i-1],layer[i]); if(y[layer[i]]<need) y[layer[i]]=need; }
  return y;
}

function medianCost(){ const cs=D.nodes.map(n=>n.cost||0).filter(c=>c>0).sort((a,b)=>a-b); return cs.length?(cs[cs.length>>1]||1):1; }
function computeLayout(){   // only reached for layout != 'compiler' (compiler uses the emitted _opos)
  if(opt.layout==='bands') layoutBands();
  else layoutSugiyama({coords:'bk'});   // sugiyama-bk
}

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
  // Fan X: index each edge among those converging into the SAME target (_xF, for ortho-late risers) and
  // among those leaving the SAME source (_xFo, for ortho-early risers), centred + sorted by the other end's y.
  for(const id in inB){ const list=inB[id], n=list.length; list.forEach((e,i)=> e._xF = n<=1?0 : (i-(n-1)/2)); }
  for(const id in outB){ const list=outB[id], n=list.length; list.forEach((e,i)=> e._xFo = n<=1?0 : (i-(n-1)/2)); }
  for(const e of edges){ if(e._tF==null)e._tF=0.5; if(e._tT==null)e._tT=0.5; if(e._xF==null)e._xF=0; if(e._xFo==null)e._xFo=0; }
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
// Edge-routing styles (opt.routing). Each returns ONE flat polyline in world space (curves tessellated)
// so the KSP Vectrosity port stays a single VectorLine per edge. Endpoint fan slots = _tF/_tT.
//   ortho-mid       stock KSP elbow: one riser at mid-X (routeEdge)
//   ortho-late      orthogonal elbow, riser near the TARGET (converging "into node")
//   ortho-early     orthogonal elbow, riser near the SOURCE (diverging "out of node")
//   junction        hyperedge bus — a shared vertical trunk per multi-child hub + branch dots
//   junction-gutter same, but multi-tier peel-offs step through the layout's clear dummy rows
//   bezier          horizontal-tangent cubic Bézier, endpoint-based (React-Flow "bumpX")
//   octilinear      metro/subway routing — horizontal, one 45° diagonal, horizontal into the target
// Fan X (opt.xfan) staggers risers that share a column; Avoid nodes (opt.avoid) detours node-crossing runs.
function routeOrthoLate(e){              // orthogonal elbow, single riser near the TARGET
  const p=anchor(byId[e.from],'RIGHT',e._tF), c=anchor(byId[e.to],'LEFT',e._tT);
  if(Math.abs(p[1]-c[1])<0.5) return [p,c];
  let rx=c[0]-Math.max(18,Math.min(60,(c[0]-p[0])*0.3));   // riser just left of the target node
  if(opt.xfan) rx=Math.max(p[0]+10, Math.min(c[0]-12, rx-(e._xF||0)*opt.xfanPitch));   // Fan X: stagger converging risers
  const k1=[rx,p[1]], k2=[rx,c[1]];
  return [p, ...chamfer(p,k1,k2,CORNER_R,CORNER_SEGS), ...chamfer(k1,k2,c,CORNER_R,CORNER_SEGS), c];
}
// ortho-early: mirror of ortho-late — the single riser sits just RIGHT of the SOURCE, so edges diverge out
// of a node immediately then run horizontally into their target row. The fan-OUT counterpart of late
// (clean divergence from a hub); Fan X here staggers by the source's out-edge index (_xFo).
function routeOrthoEarly(e){
  const p=anchor(byId[e.from],'RIGHT',e._tF), c=anchor(byId[e.to],'LEFT',e._tT);
  if(Math.abs(p[1]-c[1])<0.5) return [p,c];
  let rx=p[0]+Math.max(18,Math.min(60,(c[0]-p[0])*0.3));   // riser just right of the source node
  if(opt.xfan) rx=Math.min(c[0]-10, Math.max(p[0]+12, rx+(e._xFo||0)*opt.xfanPitch));
  const k1=[rx,p[1]], k2=[rx,c[1]];
  return [p, ...chamfer(p,k1,k2,CORNER_R,CORNER_SEGS), ...chamfer(k1,k2,c,CORNER_R,CORNER_SEGS), c];
}
// junction-bus (hyperedge): every edge leaving a multi-child source SHARES one vertical bus just right of
// the node — they emanate from the node's mid-right (fan off on the source side) into a single trunk, run
// down it, and peel off at each target's row with a JUNCTION DOT (schematic/circuit look). Collapses a
// dense fan-out into one legible trunk + branch points instead of N near-parallel risers. Each edge is
// still one flat polyline (they overlap ON the bus by design); the dots are drawn in a separate pass.
const BUS_STUB=28;                       // px from the source's right edge to the shared bus
let busX={}, junctions=[];               // busX[sourceId] = bus x; junctions = [{x,y,col}] branch dots
function buildBusRoutes(){
  busX={}; junctions=[];
  const outB={};
  for(const e of edges){ if(!(e.from in byId)||!(e.to in byId)) continue; (outB[e.from]=outB[e.from]||[]).push(e); }
  for(const id in outB) if(outB[id].length>=2) busX[id]=byId[id].pos[0]+NW()+BUS_STUB;   // only multi-child sources get a bus
}
function routeJunctionBus(e){
  const bx=busX[e.from];
  if(bx==null) return routeOrthoLate(e);                     // single-child source -> ordinary elbow
  const p=anchor(byId[e.from],'RIGHT',0.5), c=anchor(byId[e.to],'LEFT',e._tT);   // all share the node mid-right -> clean trunk
  if(Math.abs(p[1]-c[1])<0.5 && c[0]<=bx+2) return [p,c];
  junctions.push({x:bx, y:c[1], col:e.discColor||GRAY, e});   // dot where this edge leaves the bus (e = owning edge)
  return roundPolyline([p,[bx,p[1]],[bx,c[1]],c], CORNER_R, CORNER_SEGS);
}
// junction-gutter (variant A): the schematic bus, but multi-tier peel-offs STEP THROUGH the layout's dummy
// rows instead of one long horizontal at the target row. Each horizontal crosses a tier at that tier's
// DUMMY y (a row the layout kept clear of real nodes), and each vertical runs in the gutter after a column
// — so the edge never plows through a node the way plain `junction` can. Adjacent-tier edges (no dummies)
// use the plain one-gutter bus peel-off. Still one flat polyline per edge; dots as before.
function routeJunctionGutter(e){
  const bx=busX[e.from];
  if(bx==null) return routeOrthoLate(e);
  const p=anchor(byId[e.from],'RIGHT',0.5), c=anchor(byId[e.to],'LEFT',e._tT);
  const wp=e.waypoints;
  if(!wp || wp.length<=2){                                   // adjacent tier: one-gutter bus peel-off (already node-safe)
    if(Math.abs(p[1]-c[1])<0.5 && c[0]<=bx+2) return [p,c];
    junctions.push({x:bx, y:c[1], col:e.discColor||GRAY, e});
    return roundPolyline([p,[bx,p[1]],[bx,c[1]],c], CORNER_R, CORNER_SEGS);
  }
  const wy=i=> wp[i][1]+0.5*NH();                            // dummy row centre
  junctions.push({x:bx, y:wy(1), col:e.discColor||GRAY, e});
  const pts=[p,[bx,p[1]],[bx,wy(1)]];                        // into trunk, down to the first dummy row
  for(let i=1;i<wp.length-1;i++){                            // staircase: horiz across each dummy tier, vert in its gutter
    const gx=wp[i][0]+NW(), nextY = i+1<wp.length-1 ? wy(i+1) : c[1];
    pts.push([gx, wy(i)], [gx, nextY]);
  }
  pts.push(c);                                              // final gutter horizontal into the target
  return roundPolyline(pts, CORNER_R, CORNER_SEGS);
}
// avoid-nodes (variant B): a post-process — detour any LONG horizontal run that passes through a node box.
// For each offending node, hop into the gutter just past it, at a clear y above/below (whichever is nearer),
// and rejoin the row. Local + per-edge (can't guarantee global planarity, but clears the obvious crossings).
// Applied to whatever routing is active (opt.avoid); operates on the flat polyline then re-rounds.
function avoidNodes(pts){
  if(!pts || pts.length<3) return pts;
  const M=8, boxes=D.nodes.map(n=>[n.pos[0],n.pos[1],NW(),NH()]);   // [x,y,w,h]
  const out=[pts[0]];
  for(let i=1;i<pts.length;i++){
    const a=out[out.length-1], b=pts[i];
    const horiz=Math.abs(a[1]-b[1])<0.5 && Math.abs(b[0]-a[0])>NW()*0.8;   // only long horizontals offend
    if(!horiz){ out.push(b); continue; }
    const y=a[1], dir=Math.sign(b[0]-a[0]), x1=Math.min(a[0],b[0]), x2=Math.max(a[0],b[0]);
    const hit=boxes.filter(bx=> y>bx[1]+2 && y<bx[1]+bx[3]-2 && bx[0]+bx[2]>x1+2 && bx[0]<x2-2)
                   .sort((p,q)=> dir>0 ? p[0]-q[0] : q[0]-p[0]);
    for(const nb of hit){                                    // jog around each crossed node
      const above=nb[1]-M, below=nb[1]+nb[3]+M, jy=(Math.abs(y-above)<=Math.abs(y-below))?above:below;
      const L=dir>0?nb[0]-M:nb[0]+nb[2]+M, R=dir>0?nb[0]+nb[2]+M:nb[0]-M;
      out.push([L,y],[L,jy],[R,jy],[R,y]);
    }
    out.push(b);
  }
  return roundPolyline(out, CORNER_R, CORNER_SEGS);
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
    case 'ortho-late':  return routeOrthoLate(e);
    case 'ortho-early': return routeOrthoEarly(e);
    case 'junction':    return routeJunctionBus(e);
    case 'junction-gutter': return routeJunctionGutter(e);
    case 'bezier':      return routeBezier(e);
    case 'octilinear':  return routeOctilinear(e);
    default:            return routeEdge(e);   // ortho-mid (also the fallback)
  }
}


function buildGeometry(){
  computeSlots();
  if(opt.routing==='junction'||opt.routing==='junction-gutter') buildBusRoutes(); // per-source bus x + fresh dots
  for(const e of edges){
    if(!(e.from in byId)||!(e.to in byId)){ e.geom=null; continue; }
    e.geom = edgeGeom(e);   // routing variant (opt.routing)
    if(opt.avoid) e.geom = avoidNodes(e.geom);   // post-process: detour horizontals around node boxes
    const a=e.geom[e.geom.length-1], b=e.geom[e.geom.length-2];
    e.arrow={ tip:a, dir:snap4(norm(sub(a,b))) };
  }
}

// ============================ view / draw ============================
const SX=wx=>wx*cam.s+cam.x, SY=wy=>wy*cam.s+cam.y;

// ---- backdrop -------------------------------------------------------------------------
// Solid dark backdrop (a hair cool) so the bright discipline tiles read true. The in-game
// R&D grid is overridden to this SAME colour (AxeTreeRender.cs RND_BG) so prototype == KSP.
// Drop a real screenshot named `rnd-bg.png` beside this file to override with an image.
const RND_BG = '#14161c';   // keep in sync with AxeTreeRenderHost.RND_BG
let _bgImg=null, _bgTried=false;
function ensureBgImage(){ if(_bgTried) return; _bgTried=true;
  const im=new Image(); im.onload=()=>{ _bgImg=im; draw(); }; im.src='rnd-bg.png'; }   // onerror -> stay solid
function drawBackground(){
  ensureBgImage();
  const W=cv.clientWidth, H=cv.clientHeight;
  if(_bgImg && _bgImg.naturalWidth){                                   // real screenshot: cover-fit
    const iw=_bgImg.naturalWidth, ih=_bgImg.naturalHeight, s=Math.max(W/iw,H/ih);
    ctx.drawImage(_bgImg,(W-iw*s)/2,(H-ih*s)/2,iw*s,ih*s); return;
  }
  ctx.fillStyle=RND_BG; ctx.fillRect(0,0,W,H);
}

function draw(){
  ctx.setTransform(DPR,0,0,DPR,0,0);
  ctx.clearRect(0,0,cv.width,cv.height);
  drawBackground();                             // KSP-R&D-like backdrop (screenshot if present, else procedural)
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
  if(opt.routing==='junction') for(const j of junctions){   // schematic branch dots where edges peel off the bus
    const lit = !focusing || (litEdges && litEdges.has(j.e));   // dim dots off the highlighted lineage
    ctx.globalAlpha = focusing ? (lit?1:DIM_EDGE) : 1;
    ctx.fillStyle=(opt.discEdges&&!opt.baseline)?j.col:GRAY; ctx.beginPath();
    ctx.arc(SX(j.x),SY(j.y),Math.max(1.8,2.8*cam.s),0,6.2832); ctx.fill();
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
  // RESEARCHED keeps its full styling OFF the lineage too (green tile / ring / badge, just at DIM_DONE):
  // ghosting it like everything else erased the one state the player scans the tree for. Matches the
  // in-game R&D port (AxeTreeHighlight.GhostTile).
  const lockedRest = opt.progress && st===LOCKED && !inFocus;
  const doneRest = opt.progress && st===RESEARCHED;
  const doneTile = doneRest && opt.doneStyle==='tile';   // recolour the whole tile green
  const alpha = dimFocus ? (doneRest ? DIM_DONE : DIM_NODE) : (lockedRest ? 0.42 : 1);
  const fill = lockedRest ? desat(disc.color, 0.8) : (doneTile ? C_DONE_FILL : disc.color);
  ctx.globalAlpha = alpha;

  roundRect(x,y,w,h,Math.max(2,3*cam.s)); ctx.fillStyle=fill; ctx.fill();

  if(opt.progress && (!dimFocus || st===RESEARCHED)){   // ghosts keep only the DONE styling (see above)
    if(st===RESEARCHABLE){                         // AVAILABLE: bright glow ring — the actionable frontier
      ctx.save(); ctx.shadowColor=C_AVAIL; ctx.shadowBlur=Math.max(4,9*cam.s);
      ctx.strokeStyle=C_AVAIL; ctx.lineWidth=Math.max(2,3*cam.s); ctx.stroke(); ctx.restore();
    } else if(st===RESEARCHED){                     // DONE (+ the ✓ badge below, both styles)
      if(opt.doneStyle==='stamp'){ ctx.strokeStyle=C_DONE; ctx.lineWidth=Math.max(2.5,3.4*cam.s); ctx.stroke(); }   // bold green ring, disc colour kept
      else { ctx.strokeStyle='#1c6e40'; ctx.lineWidth=Math.max(1,1.5*cam.s); ctx.stroke(); }                        // darker-green edge on the green tile
    }
  }
  if(focusing && opt.halo && inFocus && n.id!==selId){   // HALO: white outline pops the lineage over the ghost
    ctx.globalAlpha=1; ctx.strokeStyle='#fff'; ctx.lineWidth=Math.max(1.5,2.4*cam.s); ctx.stroke();
  }
  if(n.id===selId){ ctx.strokeStyle='#fff'; ctx.lineWidth=3; ctx.stroke(); }
  else if(n.id===hoverId){ ctx.strokeStyle='rgba(255,255,255,.85)'; ctx.lineWidth=2; ctx.stroke(); }

  const ink = lum(disc.color)>140 ? '#10181f' : '#f3f3f3';   // contrast text (fixes dark-on-dark)
  if(opt.square){                                   // KSP-faithful: square tile = icon only, name on hover/panel
    if(opt.icons && iconReady(disc.icon)){ const s=Math.min(w,h)*0.72; ctx.globalAlpha=alpha;   // glyph a bit smaller for easier navigation (KSP ICON_SCALE)
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
      const np=(n.parts||[]).length, nu=(n.upgrades||[]).length, ng=(n.grants||[]).length, nx=(n.experiments||[]).length;
      ctx.font=`${Math.max(6,8*cam.s)}px Segoe UI,Helvetica,Arial`;
      ctx.globalAlpha=alpha*0.75;
      ctx.fillText(`T${n.tier} · ${np?np+'p':(nx?'':'—')}${nu?'+'+nu+'u':''}${ng?'+'+ng+'g':''}${nx?(np?'+':'')+nx+'e':''}`, x+w/2, y+h-8*cam.s);
    }
  }
  if((n.grants||[]).length && cam.s>0.15 && !(opt.progress && st===RESEARCHED)){   // grant marker: gold diamond (top-right) = avionics / DSN capability tier
    const gr=Math.max(3,4*cam.s), gx=x+w-gr-2*cam.s, gy=y+gr+2*cam.s;
    ctx.globalAlpha=alpha; ctx.fillStyle=GOLD;
    ctx.beginPath(); ctx.moveTo(gx,gy-gr); ctx.lineTo(gx+gr,gy); ctx.lineTo(gx,gy+gr); ctx.lineTo(gx-gr,gy); ctx.closePath(); ctx.fill();
    ctx.strokeStyle='rgba(20,14,0,.85)'; ctx.lineWidth=Math.max(.6,cam.s); ctx.stroke();
  }
  if(opt.progress && st===RESEARCHED && cam.s>0.15){    // ✓ researched badge: bold green disc + tick
    const r=Math.max(6,8.5*cam.s), cx=x+w-r-1, cy=y+r+1;
    ctx.globalAlpha=alpha;
    ctx.fillStyle=C_DONE; ctx.beginPath(); ctx.arc(cx,cy,r,0,6.2832); ctx.fill();
    ctx.strokeStyle='rgba(6,20,10,0.9)'; ctx.lineWidth=Math.max(1,1.4*cam.s); ctx.stroke();   // dark rim -> reads on the green tile too
    ctx.strokeStyle='#08140a'; ctx.lineWidth=Math.max(1.6,2.1*cam.s); ctx.lineCap='round'; ctx.lineJoin='round';
    ctx.beginPath(); ctx.moveTo(cx-r*0.42,cy+r*0.02); ctx.lineTo(cx-r*0.06,cy+r*0.42); ctx.lineTo(cx+r*0.5,cy-r*0.42); ctx.stroke();
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
function grantLabel(g){                            // friendly name for a capability-grant token (avionics tiers, DSN levels)
  const m=g.match(/^RP0Level(\d+)TrackingStation$/i); if(m) return 'Deep Space Network — Level '+m[1];
  if(/^Deep-Space-/.test(g)) return 'Shielded (deep-space) avionics tier';
  if(/^Science-Core-/.test(g)) return 'Avionics Core tier';
  return 'Capability grant';
}
// ---- part stats (engine/config data from manifest/engine-stats.tsv, wired in by build_tree.py's
// emit_prototype_data). Only engine parts carry `.engine` today; other part types have none yet --
// same field would extend to them (tank capacity, chute drag, etc.) without changing this shape. ----
function fmtNum(v,d){ return (v==null) ? '—' : (+v).toFixed(d||0).replace(/\.0+$/,''); }
function fmtRange(r,unit,d){ if(!r) return ''; const [lo,hi]=r; if(lo==null||hi==null) return '';
  return (lo===hi ? fmtNum(lo,d) : `${fmtNum(lo,d)}–${fmtNum(hi,d)}`)+unit; }
function engineSummaryHTML(e){
  const bits=[`${e.configs.length} config${e.configs.length!==1?'s':''}`];
  const thr=fmtRange(e.thrustRange,' kN',1); if(thr) bits.push(thr);
  const isp=e.ispIsFraction ? fmtRange(e.ispRange,'× TL-frac',2) : fmtRange(e.ispRange,'s',0);
  if(isp) bits.push('Isp '+isp);
  if(e.propellants.length) bits.push(esc(e.propellants[0])+(e.propellants.length>1?' +alt':''));
  return bits.join(' · ');
}
function engineTableHTML(e){
  let h='<div class="eng-wrap"><table class="engt"><thead><tr><th>Config</th><th>Gate (ref)</th>'+
        '<th>Thrust kN</th><th>Isp</th><th>Propellants</th></tr></thead><tbody>';
  for(const c of e.configs){
    const spec = c.specLevel && !/^(base|operational|prototype)$/i.test(c.specLevel) ? ` <i>(${esc(c.specLevel)})</i>` : '';
    const isp = c.ispVac!=null ? (c.ispMode==='TL-frac' ? fmtNum(c.ispVac,2)+'×†' : fmtNum(c.ispVac)) : '—';
    h+=`<tr class="${c.isBase?'base':''}"><td>${esc(c.config)}${c.isBase?' <span class="b">base</span>':''}${spec}</td>`+
       `<td>${esc(c.techTitle||'—')}</td><td>${fmtNum(c.thrustKN,1)}</td><td>${isp}</td>`+
       `<td>${esc(c.propellants||'—')}</td></tr>`;
  }
  h+='</tbody></table>';
  if(e.configs.some(c=>c.ispMode==='TL-frac')) h+='<div class="eng-note">† Isp is a fraction of this engine type\'s tech-level ceiling, not seconds</div>';
  return h+'</div>';
}
function partLiHTML(q){
  let h=`<li><div class="pt">${esc(q.title||q.name)}</div><div class="pn">${esc(q.name)}${q.mod?' · <span class="mod">'+esc(q.mod)+'</span>':''}</div>`;
  if(q.engine){
    h+=`<div class="eng-sum">⚙ ${engineSummaryHTML(q.engine)}</div>`;
    if(q.engine.configs.length>1) h+=`<details class="eng-det"><summary>upgrade path</summary>${engineTableHTML(q.engine)}</details>`;
  }
  return h+'</li>';
}
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
  if(np.length){ h+='<ul class="parts">'; for(const q of np) h+=partLiHTML(q); h+='</ul>'; }
  else h+='<div class="empty">— no parts assigned —</div>';
  if((d.upgrades||[]).length){ h+=`<div class="sec">Upgrades (${d.upgrades.length})</div><ul class="parts">`; for(const u of d.upgrades) h+=`<li><div class="pn">${esc(u)}</div></li>`; h+='</ul>'; }
  if((d.grants||[]).length){ h+=`<div class="sec">Grants — capability tiers (${d.grants.length})</div><ul class="parts">`; for(const g of d.grants) h+=`<li><div class="pt">◆ ${esc(grantLabel(g))}</div><div class="pn">${esc(g)}</div></li>`; h+='</ul>'; }
  const xs=d.experiments||[];   // Kerbalism Configure setups / gated EXPERIMENT_DEFINITIONs -- not parts, so they show nowhere else
  if(xs.length){ h+=`<div class="sec">Experiments (${xs.length})</div><ul class="parts">`;
    for(const x of xs){ const m=[x.sci?x.sci+' sci':'', x.group?'Configure: '+x.group:''].filter(Boolean).join(' · ');
      h+=`<li><div class="pt">⚗ ${esc(x.name)}</div><div class="pn">${esc(x.id||'')}${m?' · '+esc(m):''}</div></li>`; }
    h+='</ul>'; }
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
  h+=`<div class="sec">Markers</div><ul class="legend"><li>`+
     `<span class="dot" style="background:${GOLD};border-radius:2px;transform:rotate(45deg)"></span>`+
     `Avionics / DSN capability tier (grant)</li></ul>`;
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
               `<span style="color:#8a8f98">${c.l} locked</span> · ${c.sci.toLocaleString()}◈`+
               ` · <span style="color:${C_DONE}">done:${opt.doneStyle}</span> <span style="color:#6b7280">(d)</span>`;
}
function afterStateChange(){ draw(); updateHud(); if(selId) showPanel(selId); }
function showStamp(){                               // freshness chip: when + which commit the data was generated from
  const el=document.getElementById('stamp'); if(!el||!D) return;
  const m=D.meta||{};
  if(!m.generated){ el.style.display='none'; return; }
  el.innerHTML=`generated <b>${esc(m.generated)}</b>`+(m.commit?` · ${esc(m.commit)}`:'')+
               `<br>${m.nodes||D.nodes.length} nodes · ${m.parts||0} parts · ${m.grants||0} grants${m.experiments?' · '+m.experiments+' experiments':''}`;
}
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
  if(P0.has('xfan')) opt.xfan = P0.get('xfan')!=='0';
  if(P0.get('xfanpitch')) opt.xfanPitch = +P0.get('xfanpitch')||opt.xfanPitch;
  if(P0.has('avoid')) opt.avoid = P0.get('avoid')!=='0';
  buildModel(); restore();
  const rq=new URLSearchParams(location.search).get('research');   // ?research=id,id — shareable snapshot / demo
  if(rq) rq.split(',').forEach(x=>{ if(byId[x]) researched.add(x); });
  if(opt.layout!=='compiler') computeLayout(); applyLayout();
  buildGeometry(); loadIcons(); showStamp();
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
  const cb=(id,key)=>{ const el=document.getElementById(id); el.checked=opt[key];
    el.addEventListener('change',()=>{ opt[key]=el.checked; rebuild(); }); };
  cb('c_xfan','xfan'); cb('c_avoid','avoid');
  const selR=document.getElementById('s_route'); selR.value=opt.routing;
  selR.addEventListener('change',()=>{ opt.routing=selR.value; rebuild(); });
  const relayout=()=>{ if(opt.layout!=='compiler') computeLayout(); applyLayout(); buildGeometry(); fit(); draw(); };
  const selL=document.getElementById('s_layout'); selL.value=opt.layout;
  selL.addEventListener('change',()=>{ opt.layout=selL.value; relayout(); });
  const wireSp=(id,vid,key)=>{ const r=document.getElementById(id), v=document.getElementById(vid);
    r.value=opt[key]; v.textContent=opt[key].toFixed(1)+'×';
    r.addEventListener('input',()=>{ opt[key]=+r.value; v.textContent=opt[key].toFixed(1)+'×'; relayout(); }); };
  wireSp('r_spx','r_spx_v','spacingX'); wireSp('r_spy','r_spy_v','spacingY');
  const rxf=document.getElementById('r_xfan'), rxfv=document.getElementById('r_xfan_v');
  rxf.value=opt.xfanPitch; rxfv.textContent=opt.xfanPitch+'px';
  rxf.addEventListener('input',()=>{ opt.xfanPitch=+rxf.value; rxfv.textContent=opt.xfanPitch+'px'; if(opt.xfan)rebuild(); });
  document.getElementById('b_reset').addEventListener('click',()=>{ if(confirm('Reset all research progress?')){ resetProgress(); setFocus(activeFocus()); afterStateChange(); } });
  document.getElementById('b_fit').addEventListener('click',()=>{ fit(); draw(); });
  document.getElementById('zi').addEventListener('click',()=>{ cam.s=Math.min(6,cam.s*1.2); updateZoomLabel(); draw(); });
  document.getElementById('zo').addEventListener('click',()=>{ cam.s=Math.max(.05,cam.s/1.2); updateZoomLabel(); draw(); });
  document.getElementById('q').addEventListener('keydown',e=>{ if(e.key!=='Enter')return;
    const s=e.target.value.trim().toLowerCase(); if(!s)return;
    for(const n of D.nodes){ if(n.id.toLowerCase().includes(s)||n.title.toLowerCase().includes(s)||(n.experiments||[]).some(x=>x.name.toLowerCase().includes(s))||(n.parts||[]).some(p=>p.name.toLowerCase().includes(s)||(p.title||'').toLowerCase().includes(s))||(n.grants||[]).some(g=>g.toLowerCase().includes(s)||grantLabel(g).toLowerCase().includes(s))){
      selId=n.id; centerOn(n.id); setFocus(n.id); showPanel(n.id); draw(); break; } }
  });

  window.addEventListener('keydown',e=>{ if(!selId||(e.target&&e.target.tagName==='INPUT')||!opt.progress)return;
    if(e.key==='r'){ const s=stateOf(selId); if(s===RESEARCHABLE)research(selId); else if(s===LOCKED)researchPathTo(selId); afterStateChange(); }
    else if(e.key==='u'){ unresearch(selId); afterStateChange(); } });
  // 'd' toggles the researched treatment (stamp <-> tile) so you can compare them live on real nodes.
  window.addEventListener('keydown',e=>{ if(e.target&&e.target.tagName==='INPUT')return;
    if(e.key==='d'){ opt.doneStyle = opt.doneStyle==='stamp' ? 'tile' : 'stamp'; draw(); updateHud(); } });
  updateHud();
  // console / test API (also lets power users script progress)
  window.RP={ research, unresearch, researchPathTo, resetProgress, stateOf, counts, redraw:afterStateChange, get researched(){return researched;} };
}
document.addEventListener('DOMContentLoaded', init);
