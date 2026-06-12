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
    ax.set_xticklabels(DOM, fontsize=10, fontweight="bold")
    ax.set_yticklabels(SERV, fontsize=10, fontweight="bold")
    ax.set_xlabel("DOMINANT  (benefited parcel →)", fontsize=11, fontweight="bold")
    ax.set_ylabel("SERVIENT  (burdened parcel ↓)", fontsize=11, fontweight="bold")
    ax.set_title("Galleria Schedule 'A' — Easement Relationship Matrix\n"
                 "cell = number of easements (servient burdened in favour of dominant)",
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
                marks.append(f"{n_req} *")
            if n_tmp:
                marks.append(f"{n_tmp} °")
            if marks:
                sub += "\n" + "  ".join(marks)
            ax.text(j, i + 0.22, sub, ha="center", va="center", color=txtcolor,
                    fontsize=7.2, linespacing=1.3)

    cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    cbar.set_label("# easements", fontsize=9)
    fig.text(0.012, 0.018, "Each cell: count of easements (top), number of distinct purposes, "
             "and  N *  = REQUIRED?-flagged   /   N °  = temporary.   "
             "Full purpose breakdown + lossless detail in easements_matrix.html.",
             fontsize=7, color="#444")
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
        "purposes": dict(PURPOSES),
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
<title>Galleria Schedule 'A' — Easement Relationship Matrix</title>
<style>
  :root { --line:#dfe3e8; --ink:#1b2733; --muted:#65727f; --bg:#f4f6f8; --accent:#0b3d59; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
         color:var(--ink); background:var(--bg); }
  header { padding:18px 24px; background:var(--accent); color:#fff; }
  header h1 { margin:0 0 4px; font-size:19px; }
  header p { margin:0; font-size:12.5px; opacity:.85; }
  .wrap { display:flex; gap:18px; align-items:flex-start; padding:18px 24px; flex-wrap:wrap; }
  .panel { background:#fff; border:1px solid var(--line); border-radius:10px; box-shadow:0 1px 3px rgba(0,0,0,.04); }
  .matrix-panel { padding:16px; flex:1 1 560px; min-width:520px; }
  .detail-panel { padding:0; flex:1 1 420px; min-width:380px; max-height:82vh; overflow:auto; }
  table.matrix { border-collapse:separate; border-spacing:4px; width:100%; }
  table.matrix th { font-size:12px; color:var(--muted); font-weight:700; padding:4px; }
  table.matrix th.corner { text-align:right; font-size:10.5px; }
  td.cell { width:1%; min-width:78px; height:64px; border-radius:8px; cursor:pointer; vertical-align:top;
            padding:6px 7px; border:1px solid transparent; transition:transform .08s, box-shadow .08s; position:relative; }
  td.cell:hover { transform:translateY(-1px); box-shadow:0 3px 10px rgba(0,0,0,.12); }
  td.cell.empty { background:#fafbfc; cursor:default; border:1px dashed #e6e9ec; }
  td.cell.empty:hover { transform:none; box-shadow:none; }
  td.cell.sel { outline:3px solid var(--accent); outline-offset:1px; }
  .cnt { font-size:18px; font-weight:800; line-height:1; }
  .chips { margin-top:5px; display:flex; flex-wrap:wrap; gap:2px; }
  .chip { font-size:8.5px; font-weight:700; color:#fff; border-radius:3px; padding:1px 3px; line-height:1.25; }
  .mk { font-size:9px; }
  th.rowhead { text-align:right; font-size:12px; font-weight:800; color:var(--ink); padding-right:8px; white-space:nowrap; }
  .axis-note { font-size:11px; color:var(--muted); margin:2px 0 12px; }
  .legend { display:flex; flex-wrap:wrap; gap:6px 10px; margin-top:14px; padding-top:12px; border-top:1px solid var(--line); }
  .legend .item { display:flex; align-items:center; gap:5px; font-size:11px; color:var(--muted); }
  .legend .sw { width:11px; height:11px; border-radius:3px; }
  .dp-head { position:sticky; top:0; background:#fff; padding:14px 16px; border-bottom:1px solid var(--line); z-index:2; }
  .dp-head h2 { margin:0; font-size:15px; }
  .dp-head .sub { font-size:12px; color:var(--muted); margin-top:3px; }
  .dp-body { padding:6px 16px 18px; }
  .ez { border:1px solid var(--line); border-radius:9px; padding:12px 13px; margin:11px 0; }
  .ez h3 { margin:0 0 8px; font-size:13.5px; display:flex; align-items:center; gap:7px; flex-wrap:wrap; }
  .id-badge { font-family:ui-monospace,Menlo,Consolas,monospace; font-size:11px; background:#eef2f5; color:#33424f;
              padding:1px 6px; border-radius:5px; }
  .pcat { color:#fff; font-size:10.5px; font-weight:700; padding:1px 7px; border-radius:11px; }
  .badge { font-size:10px; font-weight:700; padding:1px 7px; border-radius:11px; }
  .b-req { background:#fde2e1; color:#b3261e; } .b-tmp { background:#fff3d6; color:#9a6b00; }
  .b-reg { background:#e3f0e1; color:#356a2c; } .b-tbd { background:#e8e4f5; color:#5a3fa0; }
  .ez dl { margin:0; font-size:12.2px; line-height:1.5; }
  .ez dt { color:var(--muted); font-weight:700; font-size:10.5px; text-transform:uppercase; letter-spacing:.03em; margin-top:8px; }
  .ez dd { margin:1px 0 0; }
  .ez ul.sys { margin:4px 0 0; padding-left:17px; }
  .ez ul.sys li { font-size:11.6px; margin:1px 0; }
  .ez ul.sys li .add { color:#b3261e; font-style:italic; }
  .prov { display:inline-block; font-family:ui-monospace,Menlo,Consolas,monospace; font-size:10.5px;
          background:#eef2f5; padding:0 5px; border-radius:4px; margin:2px 3px 0 0; cursor:help; }
  .placeholder { color:var(--muted); font-size:13px; padding:34px 16px; text-align:center; }
  .filters { padding:10px 24px 0; display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
  .filters label { font-size:11.5px; color:var(--muted); }
  .pill { font-size:11px; font-weight:700; padding:3px 9px; border-radius:13px; border:1px solid var(--line);
          background:#fff; cursor:pointer; color:#fff; }
  .pill.off { opacity:.32; }
  .stat { font-size:11.5px; color:var(--muted); }
  footer { padding:10px 24px 26px; font-size:11px; color:var(--muted); }
</style>
</head>
<body>
<header>
  <h1>Galleria Schedule &lsquo;A&rsquo; &mdash; Easement Relationship Matrix</h1>
  <p>Servient (burdened) &times; Dominant (benefited). Click any cell to view the full lossless detail of every easement in that relationship.</p>
</header>

<div class="filters">
  <label>Filter purposes:</label>
  <span id="pills"></span>
  <span class="stat" id="stat"></span>
</div>

<div class="wrap">
  <div class="panel matrix-panel">
    <div class="axis-note">Rows = servient parcel (burdened) &nbsp;•&nbsp; Columns = dominant parcel (benefited). Cell number = count of easements; chips = purpose categories (<span class="mk">*</span> REQUIRED? &nbsp; <span class="mk">°</span> temporary).</div>
    <div id="matrix"></div>
    <div class="legend" id="legend"></div>
  </div>
  <div class="panel detail-panel" id="detail">
    <div class="placeholder">Select a cell to inspect its easements &rarr;</div>
  </div>
</div>

<footer>Generated by <code>build_visual.py</code> from the converged dataset. Lossless: every enumerated use, system variation, proviso and termination trigger is preserved below each easement.</footer>

<script>
const DATA = /*__DATA__*/;
const {parcels, purposes, purpColor, provisos, systems, serv, dom, easements} = DATA;
let activePurposes = new Set(Object.keys(purposes));
let selKey = null;

const cellMap = {};
easements.forEach(e => {
  const k = e.servient + "|" + e.dominant;
  (cellMap[k] = cellMap[k] || []).push(e);
});

function pName(c){ return parcels[c] ? parcels[c].name : c; }

function buildPills(){
  const host = document.getElementById('pills');
  Object.entries(purposes).forEach(([code,label])=>{
    const b=document.createElement('span');
    b.className='pill'; b.textContent=code; b.style.background=purpColor[code]||'#888';
    b.title=label;
    b.onclick=()=>{ activePurposes.has(code)?activePurposes.delete(code):activePurposes.add(code);
      b.classList.toggle('off'); draw(); if(selKey) showDetail(selKey); };
    host.appendChild(b);
  });
}

function visibleEz(list){ return list.filter(e=>activePurposes.has(e.purpose)); }

function draw(){
  const t=document.createElement('table'); t.className='matrix';
  // header row
  const hr=document.createElement('tr');
  hr.appendChild(el('th','corner','servient \\ dominant'));
  dom.forEach(d=> hr.appendChild(el('th',null,d)));
  t.appendChild(hr);
  let total=0;
  serv.forEach(s=>{
    const tr=document.createElement('tr');
    const rh=document.createElement('th'); rh.className='rowhead'; rh.textContent=s; rh.title=pName(s);
    tr.appendChild(rh);
    dom.forEach(d=>{
      const k=s+"|"+d; const all=cellMap[k]||[]; const list=visibleEz(all);
      const td=document.createElement('td');
      if(!all.length){ td.className='cell empty'; tr.appendChild(td); return; }
      td.className='cell'; if(k===selKey) td.classList.add('sel');
      const n=list.length; total+=n;
      const intensity=Math.min(1, n/10);
      td.style.background = list.length ? mix("#eaf2f7","#0b3d59",intensity) : "#fafbfc";
      const cnt=el('div','cnt', String(n)); cnt.style.color = intensity>0.5?'#fff':'#0b3d59';
      td.appendChild(cnt);
      const chips=document.createElement('div'); chips.className='chips';
      const seen=new Set();
      list.forEach(e=>{ let tag=e.purpose+(e.required?'*':'')+(e.duration==='temporary'?'°':'');
        if(seen.has(tag))return; seen.add(tag);
        const c=el('span','chip',tag); c.style.background=purpColor[e.purpose]||'#888'; chips.appendChild(c); });
      td.appendChild(chips);
      td.onclick=()=>{ selKey=k; draw(); showDetail(k); };
      tr.appendChild(td);
    });
    t.appendChild(tr);
  });
  const host=document.getElementById('matrix'); host.innerHTML=''; host.appendChild(t);
  document.getElementById('stat').textContent =
    total + " of " + easements.length + " easements shown";
}

function showDetail(k){
  const [s,d]=k.split("|"); const list=visibleEz(cellMap[k]||[]);
  const host=document.getElementById('detail');
  let h = `<div class="dp-head"><h2>${s} &rarr; ${d}</h2>`+
          `<div class="sub">${pName(s)} <b>burdened</b>, in favour of ${pName(d)} &mdash; ${list.length} easement(s)</div></div>`+
          `<div class="dp-body">`;
  if(!list.length) h += `<div class="placeholder">No easements match the current purpose filter.</div>`;
  list.forEach(e=>{
    const pc = purpColor[e.purpose]||'#888';
    let badges='';
    if(e.required) badges+='<span class="badge b-req">REQUIRED?</span>';
    if(e.duration==='temporary') badges+='<span class="badge b-tmp">temporary</span>';
    if(e.status==='registered') badges+='<span class="badge b-reg">registered</span>';
    if(e.status==='placeholder') badges+='<span class="badge b-tbd">instrument TBD</span>';
    h += `<div class="ez"><h3><span class="id-badge">${e.id}</span>`+
         `<span class="pcat" style="background:${pc}">${purposes[e.purpose]}</span>${badges}</h3>`+
         `<dl>`+
         `<dt>Summary</dt><dd>${esc(e.summary)}</dd>`+
         `<dt>Scope</dt><dd>${esc(e.parts)}${e.levels?` &middot; <b>Levels:</b> ${esc(e.levels)}`:''}</dd>`+
         `<dt>Duration</dt><dd>${e.duration}${e.termination?` &mdash; ${esc(e.termination)}`:''}</dd>`+
         (e.instrument?`<dt>Instrument</dt><dd>${esc(e.instrument)} (${e.status})</dd>`:'')+
         `<dt>Use</dt><dd>${esc(e.detail)}</dd>`;
    if(e.purpose==='UTIL' && e.util){
      h+=`<dt>Enumerated systems</dt><dd><ul class="sys">`;
      e.util.systems.forEach(key=>{
        const add=e.util.deltas[key];
        h+=`<li>${esc(systems[key].title)}`+(add?` <span class="add">&mdash; ${esc(add)}</span>`:'')+`</li>`;
      });
      h+=`</ul></dd>`;
    }
    if(e.provisos && e.provisos.length){
      h+=`<dt>Provisos</dt><dd>`;
      e.provisos.forEach(p=> h+=`<span class="prov" title="${esc(provisos[p]||'')}">${p}</span>`);
      h+=`</dd>`;
    }
    h+=`</dl></div>`;
  });
  h+=`</div>`;
  host.innerHTML=h; host.scrollTop=0;
}

function buildLegend(){
  const host=document.getElementById('legend');
  Object.entries(purposes).forEach(([code,label])=>{
    const i=el('span','item'); const sw=el('span','sw'); sw.style.background=purpColor[code]||'#888';
    i.appendChild(sw); i.appendChild(document.createTextNode(code+' — '+label)); host.appendChild(i);
  });
  const note=el('span','item'); note.style.color='#444';
  note.innerHTML='<b>*</b>&nbsp;REQUIRED?&nbsp;&nbsp;<b>°</b>&nbsp;temporary'; host.appendChild(note);
}

// helpers
function el(tag,cls,txt){ const e=document.createElement(tag); if(cls)e.className=cls; if(txt!=null)e.textContent=txt; return e; }
function esc(s){ return (s==null?'':String(s)).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function mix(a,b,t){ const pa=hx(a),pb=hx(b);
  const r=Math.round(pa[0]+(pb[0]-pa[0])*t), g=Math.round(pa[1]+(pb[1]-pa[1])*t), bl=Math.round(pa[2]+(pb[2]-pa[2])*t);
  return `rgb(${r},${g},${bl})`; }
function hx(h){ h=h.replace('#',''); return [parseInt(h.substr(0,2),16),parseInt(h.substr(2,2),16),parseInt(h.substr(4,2),16)]; }

buildPills(); buildLegend(); draw();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    p1 = render_png()
    p2 = render_html()
    print(f"Wrote {p1} and {p2}")
