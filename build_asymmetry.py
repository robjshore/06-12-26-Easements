#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_asymmetry.py
==================
Surfaces ASYMMETRIES between easements of the same purpose granted for the
benefit of different parties, and identifies RECIPROCAL grants. Three lenses:

  (1) Across beneficiaries  -- same purpose, different party (does the scope /
      systems / levels / provisos differ between PK, CM and B13?).
  (2) Reciprocity           -- does a right run both ways (RC->X and X->RC) for
      a given purpose, or only one way?
  (3) Burden vs benefit     -- for reciprocal purposes, do the burden-side
      (Reserving) and benefit-side (Together With) terms differ (esp. provisos)?

Outputs (both derived from the same analysis object, so they never disagree):
  * ASYMMETRIES.md
  * easements_asymmetry.html  (interactive; click a purpose to compare)

Run:  python3 build_asymmetry.py
"""

import json
from collections import OrderedDict, defaultdict

from build_easements import EASEMENTS, PARCELS, PURPOSES, PROVISOS, SYSTEMS

PROJECT = ["PK", "CM", "B13"]            # the three project parcels (besides RC)
PURP_ORDER = [p for p in PURPOSES if p not in ("THIRDPARTY", "REGISTERED")]

# Relationship lanes we compare (exclude SUBJECT TO third-party + GRANT here):
#   burden lane  = RESERVING  (RC burdened, in favour of X)   -> party = dominant
#   benefit lane = TOGETHER   (X burdened, in favour of RC)   -> party = servient
RESERVING = [e for e in EASEMENTS if e["cat"] == "RESERVING"]
TOGETHER = [e for e in EASEMENTS if e["cat"] == "TOGETHER"]


# ---------------------------------------------------------------------------
# Normalisers for comparing fields across parties
# ---------------------------------------------------------------------------
def norm_provisos(e):
    return tuple(sorted(e["provisos"]))

def norm_util(e):
    if e["purpose"] != "UTIL" or "util" not in e:
        return None
    return tuple(sorted(e["util"]["deltas"].items()))

def util_adds(e):
    if e["purpose"] != "UTIL" or "util" not in e:
        return {}
    return e["util"]["deltas"]

def scope_kind(e):
    p = e["parts"].lower()
    if "common elements" in p:
        return "common elements"
    if p.startswith("whole"):
        return "whole parcel"
    return "specific parts"


def normalize_self(text, party):
    """Strip self-references and my REQUIRED?-annotation so that comparisons
    flag only SUBSTANTIVE differences, not a parcel naming itself."""
    if text is None:
        return ""
    t = text.replace("Marked 'REQUIRED?' in source.", "")
    t = t.replace(PARCELS[party]["name"], "«SELF»")
    t = t.replace(f"of {party}", "of «SELF»").replace(f" {party} ", " «SELF» ")
    return " ".join(t.split()).strip().rstrip(".")


def uniq_join(values, sep=" / "):
    """Dedupe while preserving order, then join."""
    seen, out = set(), []
    for v in values:
        v = str(v)
        if v not in seen:
            seen.add(v); out.append(v)
    return sep.join(out)


# ---------------------------------------------------------------------------
# Build the analysis
# ---------------------------------------------------------------------------
def party_of(e, lane):
    return e["dominant"] if lane == "burden" else e["servient"]

def group_by_purpose(records, lane):
    """ {purpose: {party: [easements]}} """
    out = OrderedDict()
    for p in PURP_ORDER:
        out[p] = {x: [] for x in PROJECT}
    for e in records:
        if e["purpose"] in out:
            out[e["purpose"]][party_of(e, lane)].append(e)
    return out

def field_diffs(members_by_party):
    """Given {party:[ez]} where each party has >=1 ez, return list of
    (field, {party: display_value}) for fields whose SUBSTANTIVE value is not
    identical across the parties that have the easement. Comparison uses a
    normalised key (self-references stripped); display uses clean values."""
    present = {p: lst for p, lst in members_by_party.items() if lst}
    diffs = []
    if len(present) < 1:
        return diffs

    def add(field, disp_fn, key_fn=None):
        disp = {p: disp_fn(p, lst) for p, lst in present.items()}
        keys = {p: (key_fn(p, lst) if key_fn else disp[p]) for p, lst in present.items()}
        if len({str(v) for v in keys.values()}) > 1:
            diffs.append((field, disp))

    add("# of easements", lambda p, l: str(len(l)))
    add("scope", lambda p, l: uniq_join(scope_kind(e) for e in l))
    add("parts / location",
        lambda p, l: uniq_join(e["parts"] for e in l),
        lambda p, l: uniq_join(normalize_self(e["parts"], p) for e in l))
    add("levels", lambda p, l: uniq_join((e["levels"] or "—") for e in l))
    add("duration", lambda p, l: uniq_join(e["duration"] for e in l))
    add("termination",
        lambda p, l: uniq_join((e["termination"] or "—") for e in l),
        lambda p, l: uniq_join(normalize_self(e["termination"] or "—", p) for e in l))
    add("REQUIRED? flag", lambda p, l: "yes" if any(e["required"] for e in l) else "no")
    add("provisos", lambda p, l: uniq_join(",".join(norm_provisos(e)) or "—" for e in l))
    add("utility system additions",
        lambda p, l: ("; ".join(f"{SYSTEMS[k][0]}: {v}" for e in l for k, v in util_adds(e).items())
                      or "base 8 systems only"))
    add("use wording",
        lambda p, l: uniq_join(e["detail"] for e in l),
        lambda p, l: uniq_join(normalize_self(e["detail"], p) for e in l))
    return diffs


def reciprocity():
    """For each (purpose, parcel) classify reciprocal / burden-only / benefit-only."""
    res_idx = defaultdict(list)   # (purpose,parcel) -> reserving ez
    ben_idx = defaultdict(list)   # (purpose,parcel) -> together ez
    for e in RESERVING:
        res_idx[(e["purpose"], e["dominant"])].append(e)
    for e in TOGETHER:
        ben_idx[(e["purpose"], e["servient"])].append(e)

    rows = []
    for p in PURP_ORDER:
        for x in PROJECT:
            b = res_idx.get((p, x), [])
            f = ben_idx.get((p, x), [])
            if not b and not f:
                status = None
            elif b and f:
                status = "reciprocal"
            elif b:
                status = "burden-only"   # RC grants to X, X does not grant back
            else:
                status = "benefit-only"  # X grants to RC, RC does not grant back
            # proviso difference between the two directions
            pdiff = None
            if b and f:
                pb = set().union(*[set(e["provisos"]) for e in b])
                pf = set().union(*[set(e["provisos"]) for e in f])
                only_burden = sorted(pb - pf)
                only_benefit = sorted(pf - pb)
                if only_burden or only_benefit:
                    pdiff = {"only_on_burden": only_burden, "only_on_benefit": only_benefit}
            rows.append(dict(purpose=p, parcel=x, status=status,
                             burden_ids=[e["id"] for e in b],
                             benefit_ids=[e["id"] for e in f],
                             proviso_diff=pdiff))
    return rows


def build_analysis():
    burden = group_by_purpose(RESERVING, "burden")   # RC -> X
    benefit = group_by_purpose(TOGETHER, "benefit")  # X -> RC
    recip = reciprocity()

    cross = {"burden": OrderedDict(), "benefit": OrderedDict()}
    for lane, grp in (("burden", burden), ("benefit", benefit)):
        for p in PURP_ORDER:
            members = grp[p]
            if not any(members.values()):
                continue
            cross[lane][p] = {
                "members": {x: [e["id"] for e in members[x]] for x in PROJECT},
                "diffs": field_diffs(members),
                "present": [x for x in PROJECT if members[x]],
                "absent": [x for x in PROJECT if not members[x]],
            }

    findings = generate_findings(burden, benefit, recip, cross)
    return dict(burden=burden, benefit=benefit, reciprocity=recip,
                cross=cross, findings=findings)


def generate_findings(burden, benefit, recip, cross):
    F = []
    # 1. coverage gaps (purpose present for some project parties but not all)
    for lane, label in (("burden", "RC grants (Reserving)"),
                        ("benefit", "RC receives (Together With)")):
        for p, info in cross[lane].items():
            if info["absent"] and info["present"]:
                F.append(dict(kind="coverage", lane=lane, purpose=p,
                              text=f"**{PURPOSES[p]}** — under *{label}* it exists for "
                                   f"{', '.join(info['present'])} but NOT for "
                                   f"{', '.join(info['absent'])}."))
    # 2. content asymmetries across beneficiaries
    for lane, label in (("burden", "RC grants (Reserving)"),
                        ("benefit", "RC receives (Together With)")):
        for p, info in cross[lane].items():
            for field, vals in info["diffs"]:
                if field == "use wording":
                    F.append(dict(kind="content", lane=lane, purpose=p,
                                  text=f"**{PURPOSES[p]}** — under *{label}* the **use wording "
                                       f"differs** between parties (see comparison)."))
                elif field == "# of easements":
                    continue  # already covered by coverage / detail
                else:
                    rendered = "; ".join(f"{k}: {v}" for k, v in vals.items())
                    F.append(dict(kind="content", lane=lane, purpose=p,
                                  text=f"**{PURPOSES[p]}** — under *{label}*, **{field}** differs "
                                       f"by party — {rendered}."))
    # 3. reciprocity classification
    for x in PROJECT:
        rec = [r["purpose"] for r in recip if r["parcel"] == x and r["status"] == "reciprocal"]
        bo = [r["purpose"] for r in recip if r["parcel"] == x and r["status"] == "burden-only"]
        fo = [r["purpose"] for r in recip if r["parcel"] == x and r["status"] == "benefit-only"]
        F.append(dict(kind="reciprocity", parcel=x,
                      text=f"**RC ↔ {x}** — reciprocal for: {', '.join(PURPOSES[p] for p in rec) or '—'}. "
                           f"Only RC→{x}: {', '.join(PURPOSES[p] for p in bo) or '—'}. "
                           f"Only {x}→RC: {', '.join(PURPOSES[p] for p in fo) or '—'}."))
    # 4. burden vs benefit proviso gaps — group parcels sharing the same pattern
    patt = OrderedDict()   # (purpose, only_burden, only_benefit) -> [parcels]
    for r in recip:
        if r["status"] == "reciprocal" and r["proviso_diff"]:
            pd = r["proviso_diff"]
            key = (r["purpose"], tuple(pd["only_on_burden"]), tuple(pd["only_on_benefit"]))
            patt.setdefault(key, []).append(r["parcel"])
    for (purpose, only_b, only_f), parcels in patt.items():
        plist = "/".join(parcels)
        bits = []
        if only_f:
            bits.append(f"the benefit side (X→RC) adds {', '.join(only_f)}")
        if only_b:
            bits.append(f"the burden side (RC→X) adds {', '.join(only_b)}")
        F.append(dict(kind="burden_benefit", purpose=purpose, parcels=parcels,
                      text=f"**{PURPOSES[purpose]}** (RC ↔ {plist}) — burden and benefit terms "
                           f"are asymmetric: {'; '.join(bits)}."))
    return F


# ===========================================================================
# MARKDOWN RENDER
# ===========================================================================
def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "---|" * len(headers)]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)

def cell_mark(ezs):
    if not ezs:
        return "·"
    s = "✓" if len(ezs) == 1 else f"✓×{len(ezs)}"
    if any(e["required"] for e in ezs):
        s += " *"
    if any(e["duration"] == "temporary" for e in ezs):
        s += " °"
    return s

def build_md(an):
    L = []; A = L.append
    A("# Galleria Schedule 'A' — Easement Asymmetry & Reciprocity Analysis")
    A("")
    A("> Companion to `EASEMENTS.md`. Compares easements of the **same purpose** granted for the "
      "benefit of **different parties**, and identifies **reciprocal** grants. Generated by "
      "`build_asymmetry.py` from the same dataset (do not hand-edit).")
    A("")
    A("**Scope of comparison:** the three project parcels — `PK` Parking, `CM` Commercial, "
      "`B13` Blocks 1 & 3 — in their two lanes relative to the Residential Condo (`RC`): "
      "*RC grants* (Reserving/Subject To) and *RC receives* (Together With). Third-party grants "
      "(City / Rogers / Enbridge) are excluded from the symmetry analysis.")
    A("")
    A("Markers: `*` = REQUIRED?-flagged · `°` = temporary.")
    A("")
    A("---")
    A("")

    # ---- Findings first (the headline) ----
    A("## 1. Headline findings")
    A("")
    groups = OrderedDict([("coverage", "Coverage gaps (granted to some parties, not others)"),
                          ("content", "Content asymmetries (same purpose, different terms)"),
                          ("reciprocity", "Reciprocity (which rights run both ways)"),
                          ("burden_benefit", "Burden-vs-benefit term asymmetries")])
    for k, title in groups.items():
        items = [f for f in an["findings"] if f["kind"] == k]
        if not items:
            continue
        A(f"### {title}")
        A("")
        for f in items:
            A(f"- {f['text']}")
        A("")

    # ---- Coverage / reciprocity grid ----
    A("## 2. Purpose coverage & reciprocity grid")
    A("")
    A("Rows = purpose. Columns = the six lanes. A purpose present on **both** `RC→X` and `X→RC` "
      "is **reciprocal** for parcel X; present on only one side is one-directional.")
    A("")
    headers = ["Purpose", "RC→PK", "RC→CM", "RC→B13", "PK→RC", "CM→RC", "B13→RC", "Reciprocal for"]
    rows = []
    for p in PURP_ORDER:
        b = an["burden"][p]; f = an["benefit"][p]
        if not any(b.values()) and not any(f.values()):
            continue
        recp = [x for x in PROJECT if b[x] and f[x]]
        rows.append([PURPOSES[p],
                     cell_mark(b["PK"]), cell_mark(b["CM"]), cell_mark(b["B13"]),
                     cell_mark(f["PK"]), cell_mark(f["CM"]), cell_mark(f["B13"]),
                     ", ".join(recp) or "—"])
    A(md_table(headers, rows))
    A("")

    # ---- Reciprocity detail ----
    A("## 3. Reciprocity map (per parcel × purpose)")
    A("")
    headers = ["Parcel", "Purpose", "Status", "RC→X (burden)", "X→RC (benefit)", "Proviso asymmetry"]
    rows = []
    for r in an["reciprocity"]:
        if r["status"] is None:
            continue
        pd = ""
        if r["proviso_diff"]:
            parts = []
            if r["proviso_diff"]["only_on_benefit"]:
                parts.append("benefit adds " + ",".join(r["proviso_diff"]["only_on_benefit"]))
            if r["proviso_diff"]["only_on_burden"]:
                parts.append("burden adds " + ",".join(r["proviso_diff"]["only_on_burden"]))
            pd = "; ".join(parts)
        rows.append([r["parcel"], PURPOSES[r["purpose"]], r["status"],
                     ", ".join(r["burden_ids"]) or "—",
                     ", ".join(r["benefit_ids"]) or "—", pd or "—"])
    A(md_table(headers, rows))
    A("")

    # ---- Cross-beneficiary comparison ----
    for lane, label in (("burden", "4. Across beneficiaries — RC grants (Reserving / Subject To)"),
                        ("benefit", "5. Across beneficiaries — RC receives (Together With)")):
        A(f"## {label}")
        A("")
        A("For each purpose, how the terms differ between the project parcels. "
          "Only fields that actually vary are shown.")
        A("")
        for p, info in an["cross"][lane].items():
            A(f"### {PURPOSES[p]}")
            present = ", ".join(info["present"]) or "—"
            absent = ", ".join(info["absent"]) or "none"
            A(f"- **Present for:** {present}  ·  **Absent for:** {absent}")
            ids = "; ".join(f"{x}: {', '.join(info['members'][x]) or '—'}" for x in PROJECT)
            A(f"- **Easements:** {ids}")
            if not info["diffs"]:
                A("- **Symmetric** across the parties present (no field differences).")
            else:
                for field, vals in info["diffs"]:
                    if field == "use wording":
                        A(f"- **{field} differs:**")
                        for x in PROJECT:
                            if x in vals:
                                A(f"    - *{x}:* {vals[x]}")
                    else:
                        rendered = " · ".join(f"**{x}** = {vals[x]}" for x in PROJECT if x in vals)
                        A(f"- **{field}:** {rendered}")
            A("")
    return "\n".join(L)


# ===========================================================================
# INTERACTIVE HTML
# ===========================================================================
PURP_COLOR = {
    "ACCESS": "#1f77b4", "CONSTR": "#ff7f0e", "UTIL": "#2ca02c", "SUPPORT": "#9467bd",
    "EGRESS": "#d62728", "CIRC": "#17becf", "WASTE": "#8c564b", "SIGN": "#e377c2",
    "TEMPCON": "#bcbd22", "AMENITY": "#7f7f7f",
}

def build_html(an, path="easements_asymmetry.html"):
    payload = {
        "purposes": {p: PURPOSES[p] for p in PURP_ORDER},
        "purpColor": PURP_COLOR,
        "provisos": dict(PROVISOS),
        "project": PROJECT,
        "burden": {p: {x: an["burden"][p][x] for x in PROJECT} for p in PURP_ORDER},
        "benefit": {p: {x: an["benefit"][p][x] for x in PROJECT} for p in PURP_ORDER},
        "reciprocity": an["reciprocity"],
        "cross": an["cross"],
        "findings": an["findings"],
        "systemsTitle": {k: SYSTEMS[k][0] for k in SYSTEMS},
    }
    html = HTML_TEMPLATE.replace("/*__DATA__*/", json.dumps(payload, ensure_ascii=False))
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Galleria — Easement Asymmetry & Reciprocity</title>
<style>
  :root{--line:#dfe3e8;--ink:#1b2733;--muted:#65727f;--bg:#f4f6f8;--accent:#0b3d59;
        --recip:#2e7d32;--burden:#1565c0;--benefit:#ad6800;}
  *{box-sizing:border-box;} body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg);}
  header{padding:18px 24px;background:var(--accent);color:#fff;}
  header h1{margin:0 0 4px;font-size:19px;} header p{margin:0;font-size:12.5px;opacity:.85;}
  .wrap{display:flex;gap:18px;align-items:flex-start;padding:18px 24px;flex-wrap:wrap;}
  .panel{background:#fff;border:1px solid var(--line);border-radius:10px;box-shadow:0 1px 3px rgba(0,0,0,.04);}
  .left{padding:16px;flex:1 1 520px;min-width:480px;} .right{padding:0;flex:1 1 440px;min-width:400px;max-height:84vh;overflow:auto;}
  h2.sec{font-size:13px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin:2px 0 10px;}
  table.grid{border-collapse:separate;border-spacing:3px;width:100%;}
  table.grid th{font-size:11px;color:var(--muted);font-weight:700;padding:4px 3px;text-align:center;}
  table.grid th.rh{text-align:left;}
  td.pc{cursor:pointer;border-radius:7px;padding:7px 9px;font-weight:700;font-size:12.5px;color:#fff;white-space:nowrap;}
  td.pc:hover{filter:brightness(1.08);} td.pc.sel{outline:3px solid var(--accent);outline-offset:1px;}
  td.lane{text-align:center;font-size:12px;border-radius:6px;padding:6px 4px;background:#fafbfc;border:1px solid #eef1f4;}
  td.lane.has{font-weight:800;} td.lane.req{color:#b3261e;} td.lane.tmp{color:#9a6b00;}
  td.recip{text-align:center;font-size:11px;font-weight:800;border-radius:6px;}
  td.recip.full{background:#e3f0e1;color:var(--recip);}
  .mk{font-size:10px;}
  .rhwrap{display:flex;flex-direction:column;gap:8px;}
  .reccard{border:1px solid var(--line);border-radius:8px;padding:8px 10px;font-size:12px;}
  .badge{font-size:10px;font-weight:700;padding:1px 7px;border-radius:11px;}
  .b-rec{background:#e3f0e1;color:#2e7d32;} .b-bo{background:#e3eefc;color:#1565c0;} .b-fo{background:#fff3d6;color:#9a6b00;}
  .dp-head{position:sticky;top:0;background:#fff;padding:14px 16px;border-bottom:1px solid var(--line);z-index:2;}
  .dp-head h2{margin:0;font-size:16px;} .dp-head .sub{font-size:12px;color:var(--muted);margin-top:3px;}
  .dp-body{padding:8px 16px 18px;}
  .lane-block{margin:12px 0;border:1px solid var(--line);border-radius:9px;overflow:hidden;}
  .lane-block .lh{padding:8px 11px;font-weight:700;font-size:12.5px;color:#fff;}
  .lh.burden{background:var(--burden);} .lh.benefit{background:var(--benefit);}
  .cmp{width:100%;border-collapse:collapse;font-size:12px;}
  .cmp th,.cmp td{border:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top;}
  .cmp th{background:#f6f8fa;font-size:11px;color:var(--muted);}
  .cmp td.field{font-weight:700;color:var(--muted);width:128px;font-size:11px;text-transform:uppercase;letter-spacing:.02em;}
  .cmp tr.diff td{background:#fff8f0;}
  .cmp .absent{color:#b3261e;font-style:italic;}
  .pill{display:inline-block;font-size:10px;font-weight:700;padding:1px 7px;border-radius:11px;margin:0 3px 2px 0;}
  .note{font-size:12px;color:var(--muted);padding:6px 0;}
  .findbox{padding:0 24px 8px;}
  .findbox details{background:#fff;border:1px solid var(--line);border-radius:9px;margin-bottom:8px;}
  .findbox summary{cursor:pointer;padding:10px 14px;font-weight:700;font-size:13px;}
  .findbox ul{margin:0;padding:4px 26px 14px;} .findbox li{font-size:12.5px;margin:5px 0;line-height:1.45;}
  code{font-family:ui-monospace,Menlo,Consolas,monospace;background:#eef2f5;padding:0 4px;border-radius:4px;font-size:11px;}
  .legend{font-size:11px;color:var(--muted);margin-top:10px;}
</style></head>
<body>
<header>
  <h1>Galleria Schedule &lsquo;A&rsquo; &mdash; Easement Asymmetry &amp; Reciprocity</h1>
  <p>Same purpose, different party: where do the terms diverge, and which rights run both ways? Click a purpose to compare.</p>
</header>

<div class="findbox" id="findbox"></div>

<div class="wrap">
  <div class="panel left">
    <h2 class="sec">Coverage &amp; reciprocity grid — click a purpose</h2>
    <div id="grid"></div>
    <div class="legend">Lanes: <b>RC&rarr;X</b> = RC burdened in favour of X (Reserving) &nbsp;|&nbsp; <b>X&rarr;RC</b> = X burdened in favour of RC (Together With). &nbsp; <span class="mk">*</span> REQUIRED? &nbsp; <span class="mk">&deg;</span> temporary. &nbsp; Green = reciprocal (both directions present).</div>
  </div>
  <div class="panel right" id="detail">
    <div class="note" style="padding:34px 16px;text-align:center;">Select a purpose to see cross-party &amp; reciprocity comparison &rarr;</div>
  </div>
</div>

<script>
const D = /*__DATA__*/;
const {purposes,purpColor,provisos,project,burden,benefit,reciprocity,cross,findings,systemsTitle}=D;
let sel=null;

function marks(list){let s='';if(list.some(e=>e.required))s+=' <span class="mk">*</span>';
  if(list.some(e=>e.duration==='temporary'))s+=' <span class="mk">&deg;</span>';return s;}
function cell(list){if(!list||!list.length)return {t:'&middot;',cls:''};
  let t=(list.length===1?'&#10003;':'&#10003;&times;'+list.length)+marks(list);
  let cls='has'+(list.some(e=>e.required)?' req':'')+(list.some(e=>e.duration==='temporary')?' tmp':'');
  return {t,cls};}

function drawGrid(){
  let h='<table class="grid"><tr><th class="rh">Purpose</th>'+
    '<th>RC&rarr;PK</th><th>RC&rarr;CM</th><th>RC&rarr;B13</th>'+
    '<th>PK&rarr;RC</th><th>CM&rarr;RC</th><th>B13&rarr;RC</th><th>recip.</th></tr>';
  Object.keys(purposes).forEach(p=>{
    const b=burden[p],f=benefit[p];
    const any=project.some(x=>(b[x]&&b[x].length)||(f[x]&&f[x].length));
    if(!any)return;
    const recp=project.filter(x=>b[x]&&b[x].length&&f[x]&&f[x].length);
    h+='<tr>';
    h+=`<td class="pc${sel===p?' sel':''}" style="background:${purpColor[p]||'#888'}" onclick="pick('${p}')">${purposes[p]}</td>`;
    project.forEach(x=>{const c=cell(b[x]);h+=`<td class="lane ${c.cls}">${c.t}</td>`;});
    project.forEach(x=>{const c=cell(f[x]);h+=`<td class="lane ${c.cls}">${c.t}</td>`;});
    h+=`<td class="recip ${recp.length?'full':''}">${recp.join(' ')||'&middot;'}</td>`;
    h+='</tr>';
  });
  h+='</table>';
  document.getElementById('grid').innerHTML=h;
}

function drawFindings(){
  const groups={coverage:'Coverage gaps',content:'Content asymmetries',
                reciprocity:'Reciprocity',burden_benefit:'Burden-vs-benefit term gaps'};
  let h='';
  Object.entries(groups).forEach(([k,title])=>{
    const items=findings.filter(f=>f.kind===k);if(!items.length)return;
    h+=`<details${k==='content'?' open':''}><summary>${title} (${items.length})</summary><ul>`;
    items.forEach(f=>h+=`<li>${mdlite(f.text)}</li>`);
    h+='</ul></details>';
  });
  document.getElementById('findbox').innerHTML=h;
}

function pick(p){sel=p;drawGrid();drawDetail(p);}

function cmpTable(lane,p){
  const info=cross[lane]&&cross[lane][p];
  if(!info)return `<div class="note">Not granted in this lane.</div>`;
  const present=info.present, absent=info.absent;
  let h='<table class="cmp"><tr><th class="field"></th>';
  project.forEach(x=>h+=`<th>${x}${present.includes(x)?'':' <span class="absent">(absent)</span>'}</th>`);
  h+='</tr>';
  // easement ids row
  h+='<tr><td class="field">easements</td>';
  project.forEach(x=>{const ids=(info.members[x]||[]);h+=`<td>${ids.length?ids.map(i=>'<code>'+i+'</code>').join(' '):'<span class="absent">—</span>'}</td>`;});
  h+='</tr>';
  if(!info.diffs.length){
    h+='<tr><td class="field">result</td><td colspan="'+project.length+'">Symmetric across the parties present (no field differences).</td></tr>';
  } else {
    info.diffs.forEach(([field,vals])=>{
      if(field==='# of easements')return;
      h+='<tr class="diff"><td class="field">'+field+'</td>';
      project.forEach(x=>{h+=`<td>${(x in vals)?esc(vals[x]):'<span class="absent">—</span>'}</td>`;});
      h+='</tr>';
    });
  }
  h+='</table>';
  if(absent.length)h=`<div class="note">Granted to <b>${present.join(', ')||'—'}</b>; <b class="absent">absent for ${absent.join(', ')}</b>.</div>`+h;
  return h;
}

function drawDetail(p){
  const recs=reciprocity.filter(r=>r.purpose===p&&r.status);
  let h=`<div class="dp-head"><h2 style="color:${purpColor[p]}">${purposes[p]}</h2>`+
        `<div class="sub">Cross-party comparison &amp; reciprocity</div></div><div class="dp-body">`;
  // reciprocity summary
  h+='<div class="rhwrap">';
  project.forEach(x=>{
    const r=recs.find(r=>r.parcel===x);
    if(!r){h+=`<div class="reccard"><b>RC &harr; ${x}:</b> <span class="absent">not granted either way</span></div>`;return;}
    let badge=r.status==='reciprocal'?'<span class="badge b-rec">reciprocal</span>':
              r.status==='burden-only'?'<span class="badge b-bo">RC&rarr;'+x+' only</span>':
              '<span class="badge b-fo">'+x+'&rarr;RC only</span>';
    let pd='';
    if(r.proviso_diff){
      const a=r.proviso_diff.only_on_benefit,bd=r.proviso_diff.only_on_burden;
      let bits=[];
      if(a.length)bits.push('benefit side ('+x+'&rarr;RC) adds <b>'+a.join(', ')+'</b>');
      if(bd.length)bits.push('burden side (RC&rarr;'+x+') adds <b>'+bd.join(', ')+'</b>');
      pd=`<div style="margin-top:4px;color:#9a6b00;">⚠ proviso asymmetry: ${bits.join('; ')}</div>`;
    } else if(r.status==='reciprocal'){pd='<div style="margin-top:4px;color:#2e7d32;">terms symmetric</div>';}
    h+=`<div class="reccard"><b>RC &harr; ${x}:</b> ${badge}${pd}</div>`;
  });
  h+='</div>';
  // burden lane
  h+='<div class="lane-block"><div class="lh burden">RC grants (Reserving / Subject To) — RC&rarr;X</div><div style="padding:8px">'+cmpTable('burden',p)+'</div></div>';
  // benefit lane
  h+='<div class="lane-block"><div class="lh benefit">RC receives (Together With) — X&rarr;RC</div><div style="padding:8px">'+cmpTable('benefit',p)+'</div></div>';
  h+='</div>';
  document.getElementById('detail').innerHTML=h;
  document.getElementById('detail').scrollTop=0;
}

function esc(s){return (s==null?'':String(s)).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function mdlite(s){return esc(s).replace(/\*\*(.+?)\*\*/g,'<b>$1</b>').replace(/\*(.+?)\*/g,'<i>$1</i>')
  .replace(/`(.+?)`/g,'<code>$1</code>').replace(/→/g,'&rarr;').replace(/↔/g,'&harr;').replace(/→/g,'&rarr;');}

drawFindings();drawGrid();
</script>
</body></html>
"""


if __name__ == "__main__":
    an = build_analysis()
    md = build_md(an)
    with open("ASYMMETRIES.md", "w", encoding="utf-8") as f:
        f.write(md)
    p = build_html(an)
    nf = len(an["findings"])
    print(f"Wrote ASYMMETRIES.md ({len(md):,} chars) and {p} — {nf} findings.")
