#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_visual.py
===============
Renders visual aids from the converged easement dataset (build_easements.py):

  1. easements_matrix.png   -- static servient x dominant heatmap (counts),
                               annotated with purpose codes + REQUIRED?/temp marks.
  2. easements_matrix.html  -- self-contained interactive matrix. Click any cell
                               to drill into the full LOSSLESS detail of every
                               easement in that relationship. No external deps.

Run:  python3 build_visual.py
"""

import json
from collections import defaultdict, OrderedDict

from build_easements import (EASEMENTS, PARCELS, PURPOSES, PROVISOS, SYSTEMS,
                             PARCEL_SHORT, PURPOSE_DESC, PURPOSE_SHORT,
                             build_markdown)  # reuse the single source of truth

# Order axes
SERV = [c for c in PARCELS if any(r["servient"] == c for r in EASEMENTS)]
DOM = [c for c in PARCELS if any(r["dominant"] == c for r in EASEMENTS)]

grid = defaultdict(lambda: defaultdict(list))
for r in EASEMENTS:
    grid[r["servient"]][r["dominant"]].append(r)


# ---------------------------------------------------------------------------
# 1. STATIC HEATMAP (matplotlib)
# ---------------------------------------------------------------------------
def render_png(path="easements_matrix.png"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap

    counts = [[len(grid[s][d]) for d in DOM] for s in SERV]
    maxc = max(max(row) for row in counts) or 1

    fig, ax = plt.subplots(figsize=(11, 6.2), dpi=150)
    cmap = LinearSegmentedColormap.from_list("teal", ["#f7fbfc", "#2c7fb8", "#0b3d59"])
    im = ax.imshow(counts, cmap=cmap, vmin=0, vmax=maxc, aspect="auto")

    ax.set_xticks(range(len(DOM)))
    ax.set_yticks(range(len(SERV)))
    ax.set_xticklabels([f"{c}\n{PARCEL_SHORT.get(c, c)}" for c in DOM], fontsize=9, fontweight="bold")
    ax.set_yticklabels([f"{PARCEL_SHORT.get(c, c)}\n({c})" for c in SERV], fontsize=9, fontweight="bold")
    ax.set_xlabel("BENEFITED parcel  →  (receives the right / \"dominant\")",
                  fontsize=11, fontweight="bold")
    ax.set_ylabel("BURDENED parcel  ↓\n(gives up the right / \"servient\")",
                  fontsize=11, fontweight="bold")
    ax.set_title("Galleria Schedule 'A' — Who grants easements to whom\n"
                 "Read a cell as: ROW parcel must allow COLUMN parcel to do N things "
                 "(N = number of easements)",
                 fontsize=12.5, fontweight="bold", pad=14)
    ax.set_xticks([x - 0.5 for x in range(1, len(DOM))], minor=True)
    ax.set_yticks([y - 0.5 for y in range(1, len(SERV))], minor=True)
    ax.grid(which="minor", color="white", linewidth=2)
    ax.tick_params(which="minor", length=0)

    for i, s in enumerate(SERV):
        for j, d in enumerate(DOM):
            rs = grid[s][d]
            n = len(rs)
            if not n:
                ax.text(j, i, "·", ha="center", va="center", color="#bbb", fontsize=14)
                continue
            n_req = sum(1 for r in rs if r["required"])
            n_tmp = sum(1 for r in rs if r["duration"] == "temporary")
            n_purp = len({r["purpose"] for r in rs})
            txtcolor = "white" if n > maxc * 0.5 else "#0b3d59"
            ax.text(j, i - 0.12, str(n), ha="center", va="center", color=txtcolor,
                    fontsize=17, fontweight="bold")
            sub = f"{n_purp} purpose{'s' if n_purp != 1 else ''}"
            marks = []
            if n_req:
                marks.append(f"{n_req} need review")
            if n_tmp:
                marks.append(f"{n_tmp} temporary")
            if marks:
                sub += "\n" + "\n".join(marks)
            ax.text(j, i + 0.26, sub, ha="center", va="center", color=txtcolor,
                    fontsize=6.6, linespacing=1.45)

    cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    cbar.set_label("number of easements", fontsize=9)
    fig.text(0.012, 0.030,
             "HOW TO READ  —  each ROW is a parcel that is BURDENED (gives up rights); "
             "each COLUMN is a parcel that is BENEFITED (receives the right).",
             fontsize=7.6, color="#111", fontweight="bold")
    fig.text(0.012, 0.012,
             "Top number = how many easements run that way. Below: number of distinct purposes, "
             "how many still need review (flagged REQUIRED?), and how many are temporary. "
             "Full plain-English breakdown in easements_matrix.html.",
             fontsize=6.8, color="#444")
    fig.tight_layout(rect=[0, 0.05, 1, 1])
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def _wrap_codes(codes, per_line=2):
    return [" ".join(codes[i:i + per_line]) for i in range(0, len(codes), per_line)]


# ---------------------------------------------------------------------------
# 2. INTERACTIVE HTML (self-contained)
# ---------------------------------------------------------------------------
PURP_COLOR = {
    "ACCESS": "#1f77b4", "CONSTR": "#ff7f0e", "UTIL": "#2ca02c", "SUPPORT": "#9467bd",
    "EGRESS": "#d62728", "CIRC": "#17becf", "WASTE": "#8c564b", "SIGN": "#e377c2",
    "TEMPCON": "#bcbd22", "AMENITY": "#7f7f7f", "THIRDPARTY": "#393b79", "REGISTERED": "#637939",
}

def render_html(path="easements_matrix.html"):
    payload = {
        "parcels": {k: dict(v) for k, v in PARCELS.items()},
        "short": PARCEL_SHORT,
        "purposes": dict(PURPOSES),
        "purposeShort": PURPOSE_SHORT,
        "purposeDesc": PURPOSE_DESC,
        "purpColor": PURP_COLOR,
        "provisos": dict(PROVISOS),
        "systems": {k: {"title": t, "components": b} for k, (t, b) in SYSTEMS.items()},
        "serv": SERV, "dom": DOM,
        "easements": EASEMENTS,
    }
    data_js = json.dumps(payload, ensure_ascii=False)

    html = HTML_TEMPLATE.replace("/*__DATA__*/", data_js)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Galleria Easements — Who grants what to whom</title>
<style>
  :root{--line:#dfe3e8;--ink:#1b2733;--muted:#65727f;--bg:#eef1f4;--accent:#0b3d59;}
  *{box-sizing:border-box;}
  body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg);}
  header{padding:20px 24px 16px;background:var(--accent);color:#fff;}
  header h1{margin:0 0 6px;font-size:20px;}
  header p{margin:0;font-size:13px;opacity:.9;max-width:1000px;line-height:1.5;}
  .explain{margin:18px 24px 0;background:#fff;border:1px solid var(--line);border-left:5px solid var(--accent);border-radius:10px;padding:14px 18px;}
  .explain h2{margin:0 0 8px;font-size:14px;text-transform:uppercase;letter-spacing:.04em;color:var(--accent);}
  .explain ol{margin:6px 0 4px;padding-left:20px;} .explain li{font-size:13px;line-height:1.6;margin:4px 0;}
  .explain .eg{background:#f4f8fb;border:1px solid #d8e6f0;border-radius:8px;padding:9px 12px;margin-top:8px;font-size:13px;}
  .keyrow{display:flex;flex-wrap:wrap;gap:8px;margin:18px 24px 0;}
  .keycard{background:#fff;border:1px solid var(--line);border-radius:9px;padding:9px 12px;font-size:12px;min-width:150px;flex:1 1 150px;}
  .keycard .code{font-family:ui-monospace,Menlo,Consolas,monospace;font-weight:800;color:var(--accent);}
  .keycard .nm{font-weight:700;} .keycard .meta{color:var(--muted);font-size:11px;margin-top:2px;}
  .wrap{display:flex;gap:18px;align-items:flex-start;padding:18px 24px;flex-wrap:wrap;}
  .panel{background:#fff;border:1px solid var(--line);border-radius:10px;box-shadow:0 1px 3px rgba(0,0,0,.05);}
  .matrix-panel{padding:18px;flex:1 1 600px;min-width:560px;}
  .detail-panel{padding:0;flex:1 1 430px;min-width:390px;max-height:84vh;overflow:auto;}
  .axiscap{font-size:12px;color:var(--muted);margin-bottom:10px;line-height:1.5;}
  .axiscap b{color:var(--ink);}
  table.matrix{border-collapse:separate;border-spacing:5px;width:100%;}
  table.matrix th.colhead{font-size:12px;font-weight:800;color:var(--ink);padding:4px 2px;text-align:center;vertical-align:bottom;}
  table.matrix th.colhead .sub{display:block;font-size:10px;font-weight:600;color:var(--muted);}
  table.matrix th.corner{font-size:10.5px;color:var(--muted);font-weight:700;text-align:right;padding-right:8px;vertical-align:bottom;max-width:120px;}
  th.rowhead{text-align:right;font-size:12px;font-weight:800;color:var(--ink);padding-right:9px;white-space:nowrap;line-height:1.25;}
  th.rowhead .sub{display:block;font-size:10px;font-weight:600;color:var(--muted);}
  td.cell{min-width:96px;height:78px;border-radius:9px;cursor:pointer;vertical-align:top;padding:7px 8px;border:1px solid transparent;transition:transform .08s,box-shadow .08s;}
  td.cell:hover{transform:translateY(-1px);box-shadow:0 4px 12px rgba(0,0,0,.14);}
  td.cell.empty{background:#f7f9fa;cursor:default;border:1px dashed #e3e7ea;}
  td.cell.empty:hover{transform:none;box-shadow:none;}
  td.cell.sel{outline:3px solid var(--accent);outline-offset:1px;}
  .cnt{font-size:20px;font-weight:800;line-height:1;}
  .cntlabel{font-size:8.5px;font-weight:600;opacity:.8;margin-top:1px;}
  .chips{margin-top:5px;display:flex;flex-wrap:wrap;gap:3px;}
  .chip{font-size:9px;font-weight:700;color:#fff;border-radius:4px;padding:1px 4px;line-height:1.3;cursor:help;}
  .flags{margin-top:4px;display:flex;flex-wrap:wrap;gap:3px;}
  .flag{font-size:8.5px;font-weight:700;border-radius:4px;padding:1px 4px;}
  .flag.rev{background:#fde2e1;color:#b3261e;} .flag.tmp{background:#fff3d6;color:#9a6b00;} .flag.note{background:#e6e0f7;color:#5a3fa0;}
  .legend{margin-top:16px;padding-top:14px;border-top:1px solid var(--line);}
  .legend h3{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin:0 0 8px;}
  .legend .grid2{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:5px 14px;}
  .legend .item{display:flex;gap:7px;font-size:11.5px;align-items:flex-start;}
  .legend .sw{width:12px;height:12px;border-radius:3px;flex:0 0 auto;margin-top:2px;}
  .legend .item b{font-weight:700;} .legend .item .d{color:var(--muted);}
  .markkey{display:flex;flex-wrap:wrap;gap:14px;margin-top:10px;font-size:11.5px;color:var(--muted);}
  .markkey .flag{margin-right:5px;}
  .dp-head{position:sticky;top:0;background:#fff;padding:15px 16px;border-bottom:1px solid var(--line);z-index:2;}
  .dp-head h2{margin:0;font-size:16px;}
  .dp-lead{font-size:13px;margin-top:7px;line-height:1.5;background:#f4f8fb;border:1px solid #d8e6f0;border-radius:8px;padding:9px 11px;}
  .dp-body{padding:8px 16px 20px;}
  .ez{border:1px solid var(--line);border-radius:10px;padding:13px 14px;margin:12px 0;}
  .ez h3{margin:0 0 4px;font-size:14px;display:flex;align-items:center;gap:8px;flex-wrap:wrap;}
  .ez .pdesc{font-size:12px;color:var(--muted);margin:0 0 8px;line-height:1.45;}
  .id-badge{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:11px;background:#eef2f5;color:#33424f;padding:1px 6px;border-radius:5px;}
  .pcat{color:#fff;font-size:11px;font-weight:700;padding:1px 8px;border-radius:11px;}
  .badge{font-size:10px;font-weight:700;padding:1px 8px;border-radius:11px;}
  .b-req{background:#fde2e1;color:#b3261e;} .b-tmp{background:#fff3d6;color:#9a6b00;}
  .b-reg{background:#e3f0e1;color:#356a2c;} .b-tbd{background:#e8e4f5;color:#5a3fa0;}
  .ez dl{margin:0;font-size:12.5px;line-height:1.55;}
  .ez dt{color:var(--muted);font-weight:700;font-size:10.5px;text-transform:uppercase;letter-spacing:.03em;margin-top:9px;}
  .ez dd{margin:1px 0 0;}
  .ez .opennote{background:#f3eefc;border:1px solid #ddd0f5;border-radius:8px;padding:8px 10px;margin-top:9px;font-size:12px;color:#4a3a78;}
  .ez ul.sys{margin:4px 0 0;padding-left:18px;} .ez ul.sys li{font-size:12px;margin:1px 0;}
  .ez ul.sys li .add{color:#b3261e;font-style:italic;}
  .prov{display:inline-block;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:10.5px;background:#eef2f5;padding:0 5px;border-radius:4px;margin:2px 3px 0 0;cursor:help;}
  .placeholder{color:var(--muted);font-size:13px;padding:40px 18px;text-align:center;line-height:1.6;}
  footer{padding:8px 24px 28px;font-size:11px;color:var(--muted);}
</style>
</head>
<body>
<header>
  <h1>Galleria Schedule &lsquo;A&rsquo; &mdash; Easements: who grants what to whom</h1>
  <p>The Galleria project is one mixed-use development split into four parts that share the same structure: the <b>Residential Condo</b>, the <b>Parking</b>, the <b>Commercial</b> units, and the future <b>Blocks&nbsp;1&nbsp;&amp;&nbsp;3</b>. Because they overlap physically, each part must grant the others legal rights (easements) &mdash; to pass through, run services, draw structural support, and so on. This grid maps every one of those rights.</p>
</header>

<div class="explain">
  <h2>How to read this grid</h2>
  <ol>
    <li>Each <b>row</b> is the parcel that is <b>burdened</b> &mdash; it <b>gives up</b> a right (the &ldquo;servient&rdquo; land).</li>
    <li>Each <b>column</b> is the parcel that is <b>benefited</b> &mdash; it <b>receives</b> the right (the &ldquo;dominant&rdquo; land).</li>
    <li>The big number in a cell is <b>how many easements</b> run that way. The coloured tags show <b>what kinds</b> of rights they are.</li>
    <li><b>Click any cell</b> to read, in plain English, exactly what each easement allows.</li>
  </ol>
  <div class="eg">Example &mdash; the cell in row <b>Residential Condo</b>, column <b>Parking</b> means: <i>&ldquo;The Residential Condo must allow the Parking parcel to do these things on/through the Condo&rsquo;s land.&rdquo;</i> If both that cell and its mirror (row Parking, column Condo) are filled, the right is <b>reciprocal</b> &mdash; granted both ways.</div>
</div>

<div class="keyrow" id="keyrow"></div>

<div class="wrap">
  <div class="panel matrix-panel">
    <div class="axiscap"><b>Rows = BURDENED parcel</b> (gives up the right) &nbsp;&bull;&nbsp; <b>Columns = BENEFITED parcel</b> (receives the right). Empty cell = no easement that direction.</div>
    <div id="matrix"></div>
    <div class="legend" id="legend"></div>
  </div>
  <div class="panel detail-panel" id="detail">
    <div class="placeholder">&#128072; Click any filled cell in the grid to see, in plain English, every easement that runs between those two parcels.</div>
  </div>
</div>

<footer>Self-contained &mdash; no internet required. Generated from the converged dataset; every enumerated use, system, proviso, open question and termination trigger is preserved in the detail panel.</footer>

<script>
const DATA = /*__DATA__*/;
const {parcels, short, purposes, purposeShort, purposeDesc, purpColor, provisos, systems, serv, dom, easements} = DATA;
let selKey = null;

const cellMap = {};
easements.forEach(e => { const k=e.servient+"|"+e.dominant; (cellMap[k]=cellMap[k]||[]).push(e); });

function pName(c){ return short[c] || (parcels[c]?parcels[c].name:c); }
function isExt(c){ return parcels[c] && parcels[c].external; }

function buildKey(){
  const host=document.getElementById('keyrow'); let h='';
  ['RC','PK','CM','B13'].forEach(c=>{
    const p=parcels[c];
    h+=`<div class="keycard"><div><span class="code">${c}</span> &mdash; <span class="nm">${p.name}</span></div>`+
       `<div class="meta">${p.parts||''}</div></div>`;
  });
  h+=`<div class="keycard" style="flex:1 1 150px"><div><span class="nm">City / Rogers / Enbridge</span></div>`+
     `<div class="meta">Outside parties that hold utility or municipal easements over the Condo lands.</div></div>`;
  host.innerHTML=h;
}

function draw(){
  const t=document.createElement('table'); t.className='matrix';
  const hr=document.createElement('tr');
  const corner=document.createElement('th'); corner.className='corner';
  corner.innerHTML='burdened&nbsp;&darr;&nbsp;/&nbsp;benefited&nbsp;&rarr;'; hr.appendChild(corner);
  dom.forEach(d=>{ const th=document.createElement('th'); th.className='colhead';
    th.innerHTML=`${d}<span class="sub">${pName(d)}</span>`; hr.appendChild(th); });
  t.appendChild(hr);
  serv.forEach(s=>{
    const tr=document.createElement('tr');
    const rh=document.createElement('th'); rh.className='rowhead';
    rh.innerHTML=`${pName(s)}<span class="sub">(${s})</span>`; tr.appendChild(rh);
    dom.forEach(d=>{
      const k=s+"|"+d; const list=cellMap[k]||[];
      const td=document.createElement('td');
      if(!list.length){ td.className='cell empty'; tr.appendChild(td); return; }
      td.className='cell'+(k===selKey?' sel':'');
      const n=list.length; const intensity=Math.min(1,n/10);
      td.style.background=mix("#eaf2f7","#0b3d59",intensity);
      const dark=intensity>0.5;
      const cnt=document.createElement('div'); cnt.className='cnt'; cnt.textContent=n;
      cnt.style.color=dark?'#fff':'#0b3d59'; td.appendChild(cnt);
      const cl=document.createElement('div'); cl.className='cntlabel';
      cl.textContent=n===1?'easement':'easements'; cl.style.color=dark?'#dce8f0':'#5a7184'; td.appendChild(cl);
      const chips=document.createElement('div'); chips.className='chips';
      const seen=new Set();
      list.forEach(e=>{ if(seen.has(e.purpose))return; seen.add(e.purpose);
        const c=document.createElement('span'); c.className='chip';
        c.textContent=purposeShort[e.purpose]||e.purpose; c.style.background=purpColor[e.purpose]||'#888';
        c.title=purposes[e.purpose]+' — '+(purposeDesc[e.purpose]||''); chips.appendChild(c); });
      td.appendChild(chips);
      const nrev=list.filter(e=>e.required).length, ntmp=list.filter(e=>e.duration==='temporary').length,
            nnote=list.filter(e=>e.note).length;
      if(nrev||ntmp||nnote){ const fl=document.createElement('div'); fl.className='flags';
        if(nrev)fl.innerHTML+=`<span class="flag rev">${nrev} need review</span>`;
        if(ntmp)fl.innerHTML+=`<span class="flag tmp">${ntmp} temporary</span>`;
        if(nnote)fl.innerHTML+=`<span class="flag note">${nnote} question</span>`;
        td.appendChild(fl); }
      td.onclick=()=>{ selKey=k; draw(); showDetail(k); };
      tr.appendChild(td);
    });
    t.appendChild(tr);
  });
  const host=document.getElementById('matrix'); host.innerHTML=''; host.appendChild(t);
}

function buildLegend(){
  const host=document.getElementById('legend');
  let h='<h3>What the coloured tags mean (types of right)</h3><div class="grid2">';
  Object.keys(purposeShort).forEach(code=>{
    if(!easements.some(e=>e.purpose===code))return;
    h+=`<div class="item"><span class="sw" style="background:${purpColor[code]||'#888'}"></span>`+
       `<span><b>${purposeShort[code]}</b> &mdash; <span class="d">${purposeDesc[code]||purposes[code]}</span></span></div>`;
  });
  h+='</div><div class="markkey">'+
     '<span><span class="flag rev">need review</span> still flagged &ldquo;REQUIRED?&rdquo; in the draft &mdash; not yet confirmed</span>'+
     '<span><span class="flag tmp">temporary</span> ends on a trigger (e.g. construction finished, or 20 years)</span>'+
     '<span><span class="flag note">question</span> an open drafting question is attached</span></div>';
  host.innerHTML=h;
}

function showDetail(k){
  const [s,d]=k.split("|"); const list=cellMap[k]||[];
  const recipKey=d+"|"+s; const reciprocal=(cellMap[recipKey]||[]).length>0;
  const host=document.getElementById('detail');
  let lead=`<b>${pName(s)}</b> must allow <b>${pName(d)}</b> to exercise the ${list.length} right`+
           `${list.length!==1?'s':''} below over the ${pName(s)} land.`;
  if(!isExt(d)&&!isExt(s)) lead+= reciprocal
      ? ` <br>&#8646; This is partly <b>reciprocal</b> &mdash; ${pName(d)} also grants rights back to ${pName(s)} (see row ${d}).`
      : ` <br>This right runs <b>one way only</b> &mdash; ${pName(d)} does not grant the same back.`;
  let h=`<div class="dp-head"><h2>${s} &rarr; ${d}</h2>`+
        `<div class="dp-lead">${lead}</div></div><div class="dp-body">`;
  list.forEach(e=>{
    const pc=purpColor[e.purpose]||'#888';
    let badges='';
    if(e.required) badges+='<span class="badge b-req">needs review</span>';
    if(e.duration==='temporary') badges+='<span class="badge b-tmp">temporary</span>';
    if(e.status==='registered') badges+='<span class="badge b-reg">registered on title</span>';
    if(e.status==='placeholder') badges+='<span class="badge b-tbd">instrument no. TBD</span>';
    h+=`<div class="ez"><h3><span class="id-badge">${e.id}</span>`+
       `<span class="pcat" style="background:${pc}">${purposes[e.purpose]}</span>${badges}</h3>`+
       `<p class="pdesc">${purposeDesc[e.purpose]||''}</p>`+
       `<dl>`+
       `<dt>What it allows</dt><dd>${esc(e.detail)}</dd>`+
       `<dt>Where</dt><dd>${esc(e.parts)}${e.levels?` &middot; <b>Levels:</b> ${esc(e.levels)}`:''}</dd>`+
       `<dt>How long</dt><dd>${e.duration==='temporary'?'Temporary':'Permanent'}${e.termination?` &mdash; ${esc(e.termination)}`:''}</dd>`+
       (e.instrument?`<dt>Registered instrument</dt><dd>${esc(e.instrument)} (${e.status})</dd>`:'');
    if(e.purpose==='UTIL'&&e.util){
      h+=`<dt>Building systems covered</dt><dd><ul class="sys">`;
      e.util.systems.forEach(key=>{const add=e.util.deltas[key];
        h+=`<li>${esc(systems[key].title)}`+(add?` <span class="add">&mdash; ${esc(add)}</span>`:'')+`</li>`;});
      h+=`</ul></dd>`;
    }
    if(e.provisos&&e.provisos.length){
      h+=`<dt>Conditions (hover for full text)</dt><dd>`;
      e.provisos.forEach(p=>h+=`<span class="prov" title="${esc(provisos[p]||'')}">${p}</span>`);
      h+=`</dd>`;
    }
    h+=`</dl>`;
    if(e.note) h+=`<div class="opennote">&#9888; <b>Open question:</b> ${esc(e.note)}</div>`;
    h+=`</div>`;
  });
  h+=`</div>`;
  host.innerHTML=h; host.scrollTop=0;
}

function esc(s){return (s==null?'':String(s)).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function mix(a,b,t){const pa=hx(a),pb=hx(b);
  const r=Math.round(pa[0]+(pb[0]-pa[0])*t),g=Math.round(pa[1]+(pb[1]-pa[1])*t),bl=Math.round(pa[2]+(pb[2]-pa[2])*t);
  return `rgb(${r},${g},${bl})`;}
function hx(h){h=h.replace('#','');return [parseInt(h.substr(0,2),16),parseInt(h.substr(2,2),16),parseInt(h.substr(4,2),16)];}

buildKey(); buildLegend(); draw();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    p1 = render_png()
    p2 = render_html()
    print(f"Wrote {p1} and {p2}")
