"""Excel Accelerator — front door.

One page, four scenarios: what each demo is, links to the notebooks, the
walkthrough doc tab, the recording, and the live assets — plus a health
chip and a Reset button per scenario (backed by the "Excel Accelerator —
Reset" job created by shared/create_reset_job.py).

Everything is env-var driven with working defaults so the app deploys on
any workspace unchanged. Synthetic data throughout; see the repo README.
"""
import os
import threading
import time

from databricks.sdk import WorkspaceClient
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

CATALOG = os.getenv("CATALOG_NAME", "lr_dev_aws_us_catalog")
SCHEMA = os.getenv("SCHEMA_NAME", "actuarial_excel_demo")
FOLDER = os.getenv("EXCEL_FOLDER_PATH", "/Workspace/Shared/actuarial-excel-accelerator")
DOC_URL = os.getenv("DOC_URL",
                    "https://docs.google.com/document/d/1BiHEgVHeKHMWFzE5JFgZfWaHBvO3F8jgfSPfVgaEags/edit")
RESET_JOB_NAME = os.getenv("RESET_JOB_NAME", "Excel Accelerator — Reset")
REPO_URL = "https://github.com/wryszka/actuarial-excel-accelerator"

FQ = f"{CATALOG}.{SCHEMA}"

SCENARIOS = [
    {
        "id": "uc1",
        "title": "1 · The VBA nobody understands",
        "strap": "A legacy macro cleans the monthly claims bordereau — nobody remembers how.",
        "wow": "Genie Code explains the VBA (it's been silently dropping claims for years), "
               "converts it, and a file-arrival job runs it unattended.",
        "folder": f"{FOLDER}/demo_00_vba_csv_etl",
        "doc_tab": os.getenv("DOC_TAB_UC1", "t.bzv4poipaxlz"),
        "youtube": os.getenv("YT_UC1", ""),
        "tables": ["brd_bronze_claims", "brd_silver_claims", "brd_quarantine"],
        "reset_note": "Drops the brd_ tables and clears incoming/ (~1 min).",
    },
    {
        "id": "uc2",
        "title": "2 · From spreadsheet model to governed model",
        "strap": "A Standard-Formula capital model in a workbook — one file per entity.",
        "wow": "The model becomes a versioned asset in Unity Catalog: a model version IS a "
               "calibration. 2026 vs 2025 on identical inputs = the capital impact in seconds.",
        "folder": f"{FOLDER}/demo_02b_sf_model_uc",
        "doc_tab": os.getenv("DOC_TAB_UC2", "t.qow31u7gomkp"),
        "youtube": os.getenv("YT_UC2", ""),
        "tables": ["sfm_inputs", "sfm_results", "sfm_impact"],
        "model": f"{FQ}.sfm_scr_model",
        "reset_note": "Drops the sfm_ tables; registered model versions are kept (~1 min).",
    },
    {
        "id": "uc3",
        "title": "3 · Ad-hoc analytics: pivots → Genie & AI/BI",
        "strap": "The claims listing lands in Excel and the pivot ritual begins.",
        "wow": "The same table, governed: Genie answers in plain English, the dashboard is "
               "published live — then more tables for what Excel can't hold.",
        "folder": f"{FOLDER}/demo_03_experience_genie",
        "doc_tab": os.getenv("DOC_TAB_UC3", "t.8r228vdd3l38"),
        "youtube": os.getenv("YT_UC3", ""),
        "tables": ["exp_claims_listing", "exp_gold_experience", "exp_gold_triangle"],
        "genie_title": "Claims Analytics — Actuarial Excel Accelerator",
        "dashboards": ["Use Case 3 — Claims Ad-hoc Analytics",
                       "Demo 3 — Portfolio Experience Monitoring"],
        "reset_note": "Full world regen + Genie space back to its one-table starter (~15 min).",
    },
    {
        "id": "uc4",
        "title": "4 · The monthly blend — Lakeflow Designer",
        "strap": "The join–clean–aggregate canvas living in a desktop ETL tool today.",
        "wow": "The same canvas, no-code, on the platform — backed by real code, lineage and a "
               "schedule. Provably equal to the coded pipeline.",
        "folder": f"{FOLDER}/demo_04_lakeflow_designer",
        "doc_tab": os.getenv("DOC_TAB_UC4", "t.xx63b7kbyr11"),
        "youtube": os.getenv("YT_UC4", ""),
        "tables": ["exp_designer_claims_src", "exp_designer_premium_src"],
        "optional_tables": ["exp_designer_experience"],
        "reset_note": "Rebuilds the canvas source tables and drops the canvas output (~2 min).",
    },
]

app = FastAPI(title="Excel Accelerator")
_w = None


def w() -> WorkspaceClient:
    global _w
    if _w is None:
        _w = WorkspaceClient()
    return _w


_cache = {"status": None, "ts": 0.0}
_lock = threading.Lock()


def _table_exists(name: str) -> bool:
    try:
        return bool(w().tables.exists(full_name=f"{FQ}.{name}").table_exists)
    except Exception:
        return False


def _compute_status():
    host = w().config.host.rstrip("/")
    genie = {}
    try:
        for s in w().api_client.do("GET", "/api/2.0/genie/spaces").get("spaces", []):
            genie[s.get("title")] = s.get("space_id")
    except Exception:
        pass
    dashboards = {}
    try:
        for d in w().lakeview.list():
            dashboards[d.display_name] = d.dashboard_id
    except Exception:
        pass

    out = []
    for sc in SCENARIOS:
        missing = [t for t in sc["tables"] if not _table_exists(t)]
        ok = not missing
        detail = "ready" if ok else f"missing: {', '.join(missing)}"
        if sc.get("model"):
            try:
                w().registered_models.get(full_name=sc["model"])
            except Exception:
                ok, detail = False, (detail + " · model missing").lstrip(" ·")
        links = []
        if sc.get("genie_title") and genie.get(sc["genie_title"]):
            links.append({"label": "Genie space",
                          "href": f"{host}/genie/rooms/{genie[sc['genie_title']]}"})
        for dn in sc.get("dashboards", []):
            if dashboards.get(dn):
                links.append({"label": dn.split("—")[-1].strip(),
                              "href": f"{host}/dashboardsv3/{dashboards[dn]}/published"})
        if sc.get("model"):
            links.append({"label": "Registered model",
                          "href": f"{host}/explore/data/models/{CATALOG}/{SCHEMA}/sfm_scr_model"})
        pend = [t for t in sc.get("optional_tables", []) if not _table_exists(t)]
        out.append({"id": sc["id"], "ok": ok, "detail": detail, "live": links,
                    "pending": (f"canvas output pending ({', '.join(pend)})" if pend else "")})
    return {"scenarios": out, "host": host}


@app.get("/api/status")
def status(refresh: bool = False):
    with _lock:
        if refresh or _cache["status"] is None or time.time() - _cache["ts"] > 60:
            _cache["status"] = _compute_status()
            _cache["ts"] = time.time()
        return JSONResponse(_cache["status"])


def _reset_job_id():
    j = next(iter(w().jobs.list(name=RESET_JOB_NAME)), None)
    return j.job_id if j else None


@app.post("/api/reset/{scenario}")
def reset(scenario: str):
    if scenario not in {"uc1", "uc2", "uc3", "uc4", "all"}:
        raise HTTPException(400, "unknown scenario")
    job_id = _reset_job_id()
    if not job_id:
        raise HTTPException(503, f"Reset job '{RESET_JOB_NAME}' not found — "
                                 "run shared/create_reset_job first.")
    r = w().jobs.run_now(job_id=job_id, job_parameters={"scenario": scenario})
    return {"run_id": r.run_id, "job_id": job_id}


@app.get("/api/reset_status")
def reset_status():
    job_id = _reset_job_id()
    if not job_id:
        return {"active": []}
    host = w().config.host.rstrip("/")
    active = []
    for r in w().jobs.list_runs(job_id=job_id, active_only=True):
        active.append({"run_id": r.run_id,
                       "url": f"{host}/jobs/{job_id}/runs/{r.run_id}"})
    return {"active": active, "job_url": f"{host}/jobs/{job_id}"}


def _card(sc) -> str:
    yt = (f'<a class="lnk" href="{sc["youtube"]}" target="_blank">▶ Watch the recording</a>'
          if sc["youtube"] else '<span class="lnk soon">▶ Recording — coming soon</span>')
    return f"""
    <div class="card" id="{sc['id']}">
      <div class="chip" id="chip-{sc['id']}">checking…</div>
      <h2>{sc['title']}</h2>
      <p class="strap">{sc['strap']}</p>
      <p class="wow">{sc['wow']}</p>
      <div class="links">
        <a class="lnk" href="HOST#workspace{sc['folder']}" target="_blank">📓 Open the notebooks</a>
        <a class="lnk" href="{DOC_URL}?tab={sc['doc_tab']}" target="_blank">📄 Walkthrough</a>
        {yt}
        <span class="live" id="live-{sc['id']}"></span>
      </div>
      <div class="resetrow">
        <button class="reset" onclick="doReset('{sc['id']}', this)">Reset scenario</button>
        <span class="note">{sc['reset_note']}</span>
      </div>
    </div>"""


@app.get("/", response_class=HTMLResponse)
def index():
    cards = "".join(_card(sc) for sc in SCENARIOS)
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Excel Accelerator</title>
<style>
 body{{font-family:-apple-system,'Segoe UI',Helvetica,Arial,sans-serif;margin:0;
      background:#0e1a20;color:#e8eef1}}
 .wrap{{max-width:1080px;margin:0 auto;padding:32px 20px 60px}}
 h1{{font-size:26px;margin:0 0 4px}} .sub{{color:#9fb3bd;margin:0 0 26px}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(440px,1fr));gap:18px}}
 .card{{background:#15242c;border:1px solid #24404d;border-radius:12px;padding:20px;position:relative}}
 .card h2{{font-size:17px;margin:2px 0 8px}} .strap{{color:#9fb3bd;font-size:13px;margin:0 0 8px}}
 .wow{{font-size:13.5px;line-height:1.45;margin:0 0 14px}}
 .chip{{position:absolute;top:16px;right:16px;font-size:11px;padding:3px 9px;border-radius:20px;
       background:#24404d;color:#9fb3bd}}
 .chip.ok{{background:#123c2a;color:#5fd39a}} .chip.bad{{background:#43222a;color:#ff8f9e}}
 .chip.busy{{background:#3d3417;color:#ffd479}}
 .links{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px}}
 .lnk{{font-size:12.5px;color:#7fd0ff;text-decoration:none;background:#1a2f3a;padding:5px 10px;
      border-radius:7px;border:1px solid #24404d}}
 .lnk:hover{{border-color:#7fd0ff}} .lnk.soon{{color:#6b8593;cursor:default}}
 .resetrow{{display:flex;align-items:center;gap:10px;border-top:1px solid #22333c;padding-top:12px}}
 .reset{{background:#43222a;color:#ff8f9e;border:1px solid #6b3540;border-radius:7px;
        padding:6px 12px;font-size:12.5px;cursor:pointer}}
 .reset:hover{{background:#552a34}} .reset:disabled{{opacity:.5;cursor:wait}}
 .note{{font-size:11.5px;color:#6b8593}}
 .foot{{margin-top:28px;font-size:12px;color:#6b8593}}
 .foot a{{color:#7fd0ff}}
 .topline{{display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:10px}}
 .resetall{{font-size:12.5px}}
</style></head><body><div class="wrap">
 <div class="topline">
   <div><h1>Excel Accelerator</h1>
   <p class="sub">Four migrations off the spreadsheet estate — run them, break them, reset them.</p></div>
   <button class="reset resetall" onclick="doReset('all', this)">Reset everything</button>
 </div>
 <div class="grid">{cards}</div>
 <div class="foot">
   <span id="runbar"></span>
   <a href="{DOC_URL}" target="_blank">Full demo guide</a> ·
   <a href="{REPO_URL}" target="_blank">GitHub</a> ·
   About this demo: all data is synthetic; no customer data is used.
 </div>
</div>
<script>
async function load(refresh) {{
  const r = await fetch('/api/status' + (refresh ? '?refresh=true' : ''));
  const s = await r.json();
  document.querySelectorAll('a.lnk').forEach(a => {{
    if (a.href.includes('HOST#workspace')) a.href = a.href.replace('HOST#workspace', s.host + '/#workspace');
  }});
  for (const sc of s.scenarios) {{
    const chip = document.getElementById('chip-' + sc.id);
    chip.textContent = sc.ok ? (sc.pending ? 'ready · ' + sc.pending : 'ready') : sc.detail;
    chip.className = 'chip ' + (sc.ok ? 'ok' : 'bad');
    const live = document.getElementById('live-' + sc.id);
    live.innerHTML = sc.live.map(l =>
      `<a class="lnk" target="_blank" href="${{l.href}}">⚡ ${{l.label}}</a>`).join(' ');
  }}
}}
async function pollRuns() {{
  const r = await fetch('/api/reset_status'); const s = await r.json();
  const bar = document.getElementById('runbar');
  if (s.active && s.active.length) {{
    bar.innerHTML = `⏳ reset running — <a target="_blank" href="${{s.active[0].url}}">watch</a> · `;
    document.querySelectorAll('.chip').forEach(c => {{ c.textContent = 'resetting…'; c.className='chip busy'; }});
    setTimeout(pollRuns, 15000);
  }} else {{ bar.innerHTML = ''; load(true); }}
}}
async function doReset(sc, btn) {{
  if (!confirm('Reset ' + sc + ' back to its original state?')) return;
  btn.disabled = true;
  try {{
    const r = await fetch('/api/reset/' + sc, {{method: 'POST'}});
    if (!r.ok) alert((await r.json()).detail || 'reset failed');
    else pollRuns();
  }} finally {{ btn.disabled = false; }}
}}
load(false); pollRuns();
</script></body></html>"""
