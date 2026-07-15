"""Excel Accelerator — front door.

Light, Bricksurance-branded single-file app matching the Actuarial
Workbench's visual language: a landing page with four tiles, a side
panel with the four demos, and a page per demo with the recording,
the assets and a Reset button.

Resets run via the job "Excel Accelerator — Reset" (created by
shared/create_reset_job.py); the app's service principal only holds
CAN_MANAGE_RUN on it. Env-var driven with working defaults so the app
deploys on any workspace unchanged. Synthetic data throughout.
"""
import json
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
ENTITY = os.getenv("ENTITY_NAME", "Bricksurance SE")
REPO_URL = "https://github.com/wryszka/actuarial-excel-accelerator"

FQ = f"{CATALOG}.{SCHEMA}"

SCENARIOS = [
    {
        "id": "uc1",
        "n": 1,
        "title": "The VBA nobody understands",
        "strap": "A legacy macro cleans the monthly claims bordereau — nobody remembers how.",
        "wow": "Genie Code explains the VBA — revealing it has been silently dropping claims "
               "for years — then converts it. A file-arrival job runs the pipeline unattended, "
               "and reconciliation ties out to the penny.",
        "folder": f"{FOLDER}/demo_00_vba_csv_etl",
        "doc_tab": os.getenv("DOC_TAB_UC1", "t.bzv4poipaxlz"),
        "youtube": os.getenv("YT_UC1", ""),
        "tables": ["brd_bronze_claims", "brd_silver_claims", "brd_quarantine"],
        "does": "Migrates a legacy Excel + VBA data-cleaning process to a governed, "
                "automated Databricks pipeline — and shows you can trust the result.",
        "steps": [
            "The 'before': an actuary downloads the monthly claims bordereau CSV and runs "
            "an old Excel macro that cleans it (dedupe, parse dates, map status codes, "
            "compute incurred) and exports a standardised file for the pricing system.",
            "Paste the VBA into Genie Code and ask what it does — it reveals the macro has "
            "been silently dropping claims with unparseable dates for years.",
            "Ask Genie Code to convert it: you get a notebook that applies the same rules, "
            "landing bronze → silver, and quarantines the bad rows instead of dropping them.",
            "Reconcile: the notebook's output ties out to the old Excel file to the penny — "
            "plus the claims Excel was throwing away are now visible.",
            "Automate it: a file-arrival job runs the whole pipeline the moment next month's "
            "file lands in the volume. No one runs anything by hand again.",
        ],
        "reset_note": "Drops the brd_ tables and clears incoming/ (~1 min).",
    },
    {
        "id": "uc2",
        "n": 2,
        "title": "From spreadsheet model to governed model",
        "strap": "A Standard-Formula capital model in a workbook — one file per entity.",
        "wow": "The model becomes a versioned asset in Unity Catalog: a model version IS a "
               "calibration. Running 2026 vs 2025 on identical inputs shows the group capital "
               "impact in seconds — by module, by entity.",
        "folder": f"{FOLDER}/demo_02b_sf_model_uc",
        "doc_tab": os.getenv("DOC_TAB_UC2", "t.qow31u7gomkp"),
        "youtube": os.getenv("YT_UC2", ""),
        "tables": ["sfm_inputs", "sfm_results", "sfm_impact"],
        "model": f"{FQ}.sfm_scr_model",
        "does": "Turns a Solvency-II-style capital model that lives in a spreadsheet into a "
                "versioned, governed model in Unity Catalog — then runs it across a whole "
                "group of entities and measures a calibration change in seconds.",
        "steps": [
            "The 'before': a Standard-Formula SCR model in an Excel workbook — one file per "
            "entity, with a calibration block (regulatory parameters) typed in by hand.",
            "The model's formulas are re-implemented as an MLflow model and registered in "
            "Unity Catalog; the 2025 calibration is logged with it, so a model version IS a "
            "calibration (aliases @cal_2025, @cal_2026, @champion).",
            "Score all 100 entities in one pass from a governed inputs table — every result "
            "row carries the model version that produced it, so nothing is unexplained.",
            "Parity: for the workbook's entity, the registered model matches the spreadsheet "
            "to four decimal places.",
            "The 2026 calibration arrives → register version 2 → re-score → an impact table "
            "shows the group capital change by entity and by risk module. In the spreadsheet "
            "world this is weeks of rework; here it is seconds, and fully reproducible.",
        ],
        "reset_note": "Drops the sfm_ tables; registered model versions are kept (~1 min).",
    },
    {
        "id": "uc3",
        "n": 3,
        "title": "Ad-hoc analytics: pivots → Genie & AI/BI",
        "strap": "The claims listing lands in Excel and the pivot ritual begins.",
        "wow": "The same table, governed: Genie answers the pivot questions in plain English, "
               "the dashboard is published live to everyone — then more tables join for the "
               "analysis Excel can't hold.",
        "folder": f"{FOLDER}/demo_03_experience_genie",
        "doc_tab": os.getenv("DOC_TAB_UC3", "t.8r228vdd3l38"),
        "youtube": os.getenv("YT_UC3", ""),
        "tables": ["exp_claims_listing", "exp_gold_experience", "exp_gold_triangle"],
        "genie_title": "Claims Analytics — Actuarial Excel Accelerator",
        "dashboards": ["Use Case 3 — Claims Ad-hoc Analytics",
                       "Demo 3 — Portfolio Experience Monitoring"],
        "does": "Replaces the monthly pivot-table ritual with Genie (ask questions in plain "
                "English) and a published AI/BI dashboard everyone can see — over a book far "
                "larger than Excel can open.",
        "steps": [
            "The 'before': a claims listing lands in Excel and the analyst builds pivots — "
            "claims by line of business and status, average severity by region, largest "
            "open claims, the monthly trend.",
            "Point at the same data as a governed table (exp_claims_listing, ~146k claims), "
            "already documented for Genie.",
            "Quick-setup a Genie space over that one table and ask the pivot questions in "
            "plain English — click 'show code' to reveal the SQL it wrote.",
            "Publish an AI/BI dashboard of the same views, shared live with everyone — no "
            "emailing a workbook around.",
            "Extend: add premium, loss-ratio and development tables to the space and ask the "
            "questions Excel can't hold — 'why is Motor 2023 worse than 2021?' — over the "
            "full ~800k-transaction book.",
        ],
        "reset_note": "Full world regen + Genie space back to its one-table starter (~15 min).",
    },
    {
        "id": "uc4",
        "n": 4,
        "title": "The monthly blend — Lakeflow Designer",
        "strap": "The join–clean–aggregate canvas living in a desktop ETL tool today.",
        "wow": "The same canvas, no-code, on the platform — backed by real code, lineage and a "
               "schedule. Provably equal to the coded pipeline, so the analyst's path and the "
               "engineers' path meet on one governed platform.",
        "folder": f"{FOLDER}/demo_04_lakeflow_designer",
        "doc_tab": os.getenv("DOC_TAB_UC4", "t.xx63b7kbyr11"),
        "youtube": os.getenv("YT_UC4", ""),
        "tables": ["dsg_claims_src", "dsg_premium_src", "dsg_benchmark"],
        "optional_tables": ["dsg_experience"],
        "does": "Rebuilds the kind of join–clean–aggregate workflow analysts run in desktop "
                "ETL tools (Alteryx, Power Query) as a no-code Lakeflow Designer canvas — "
                "governed, with real code behind it, provably equal to a coded pipeline.",
        "steps": [
            "The 'before': the monthly blend built as a drag-and-drop canvas on someone's "
            "desktop — a per-seat licence, no lineage, output emailed around.",
            "In Lakeflow Designer, add the source tables (claims, premium, the segment "
            "lookup) — or drag a CSV straight onto the canvas.",
            "Build the blend visually: join claims to the lookup (the VLOOKUP), aggregate by "
            "line of business and accident year (the pivot), blend in premium, and add a "
            "loss_ratio column by describing it to Genie Code.",
            "Write the result to a governed table and run it. Parity check: it matches the "
            "coded pipeline's benchmark, cell for cell.",
            "The close — open the real code behind the canvas, view its lineage in Unity "
            "Catalog, and schedule it as a monthly job. From an uncontrolled desktop tool to "
            "a fully governed platform, with the code written for you.",
        ],
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
    genie, dashboards = {}, {}
    try:
        for s in w().api_client.do("GET", "/api/2.0/genie/spaces").get("spaces", []):
            genie[s.get("title")] = s.get("space_id")
    except Exception:
        pass
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
            links.append({"label": "Genie space", "kind": "genie",
                          "href": f"{host}/genie/rooms/{genie[sc['genie_title']]}"})
        for dn in sc.get("dashboards", []):
            if dashboards.get(dn):
                links.append({"label": dn.split("—")[-1].strip() + " (dashboard)",
                              "kind": "dashboard",
                              "href": f"{host}/dashboardsv3/{dashboards[dn]}/published"})
        if sc.get("model"):
            links.append({"label": "Registered model — sfm_scr_model", "kind": "model",
                          "href": f"{host}/explore/data/models/{CATALOG}/{SCHEMA}/sfm_scr_model"})
        pend = [t for t in sc.get("optional_tables", []) if not _table_exists(t)]
        out.append({"id": sc["id"], "ok": ok, "detail": detail, "live": links,
                    "pending": ("canvas output pending" if pend else "")})
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
    active = [{"run_id": r.run_id, "url": f"{host}/jobs/{job_id}/runs/{r.run_id}"}
              for r in w().jobs.list_runs(job_id=job_id, active_only=True)]
    return {"active": active, "job_url": f"{host}/jobs/{job_id}"}


CLIENT_SCENARIOS = [
    {k: sc[k] for k in ("id", "n", "title", "strap", "wow", "does", "steps",
                        "folder", "doc_tab", "youtube", "reset_note")}
    for sc in SCENARIOS
]


@app.get("/", response_class=HTMLResponse)
def index():
    data = json.dumps({"scenarios": CLIENT_SCENARIOS, "docUrl": DOC_URL,
                       "repoUrl": REPO_URL, "entity": ENTITY})
    return HTML_PAGE.replace("__DATA__", data)


HTML_PAGE = """<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Excel Accelerator — Bricksurance</title>
<style>
:root{
  --blue-50:#eff6ff; --blue-100:#dbeafe; --blue-200:#bfdbfe; --blue-300:#93c5fd;
  --blue-700:#1d4ed8; --blue-800:#1e40af; --blue-900:#1e3a8a;
  --gray-50:#f8fafc; --gray-100:#f1f5f9; --gray-200:#e2e8f0; --gray-400:#94a3b8;
  --gray-500:#64748b; --gray-600:#475569; --gray-900:#0f172a;
  --em-100:#d1fae5; --em-300:#a7f3d0; --em-800:#065f46;
  --am-100:#fef3c7; --am-300:#fcd34d; --am-800:#92400e;
  --red-100:#fee2e2; --red-300:#fecaca; --red-700:#b91c1c;
}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,'Segoe UI',Helvetica,Arial,sans-serif;
     background:var(--gray-50);color:var(--gray-900);font-size:14px}
a{color:var(--blue-700)}
.layout{display:flex;min-height:100vh}
/* ── side panel ── */
.side{width:250px;background:#fff;border-right:1px solid var(--gray-200);
      padding:20px 14px;display:flex;flex-direction:column;gap:2px;flex-shrink:0}
.brand{display:flex;gap:10px;align-items:center;padding:4px 8px 16px}
.brand .mark{width:36px;height:36px;border-radius:9px;background:var(--blue-700);
      color:#fff;font-weight:800;font-size:18px;display:flex;align-items:center;
      justify-content:center}
.brand .t1{font-weight:800;font-size:14px;line-height:1.15}
.brand .t2{font-size:10px;color:var(--gray-500);text-transform:uppercase;
      letter-spacing:.08em;font-weight:700;margin-top:2px}
.navlbl{font-size:10px;text-transform:uppercase;letter-spacing:.1em;font-weight:800;
      color:var(--gray-400);padding:10px 8px 4px}
.nav{display:block;padding:9px 10px;border-radius:9px;color:var(--gray-600);
     text-decoration:none;font-weight:600;font-size:13px;line-height:1.3}
.nav .no{color:var(--blue-700);font-weight:800;margin-right:7px}
.nav:hover{background:var(--gray-100)}
.nav.active{background:var(--blue-50);color:var(--blue-900)}
.side .spacer{flex:1}
.side .foot{border-top:1px solid var(--gray-200);padding-top:12px;display:flex;
     flex-direction:column;gap:6px}
.side .foot a{font-size:12px;text-decoration:none;color:var(--gray-500);padding:2px 8px}
.side .foot a:hover{color:var(--blue-700)}
.resetall{margin:2px 8px 0;font-size:12px;background:#fff;border:1px solid var(--red-300);
     color:var(--red-700);border-radius:8px;padding:7px 10px;cursor:pointer;font-weight:600}
.resetall:hover{background:var(--red-100)}
/* ── main ── */
.main{flex:1;padding:34px 40px 60px;max-width:1000px}
.eyebrow{font-size:11px;text-transform:uppercase;letter-spacing:.14em;
     color:var(--blue-700);font-weight:800}
h1{font-size:27px;letter-spacing:-.01em;margin:6px 0 6px}
.sub{color:var(--gray-500);font-size:15px;margin:0 0 28px;max-width:640px;line-height:1.5}
/* landing tiles */
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(380px,1fr));gap:16px}
.tile{background:#fff;border:2px solid var(--blue-200);border-radius:14px;padding:18px;
     text-decoration:none;color:inherit;display:flex;flex-direction:column;
     transition:box-shadow .15s,border-color .15s}
.tile:hover{border-color:var(--blue-300);box-shadow:0 8px 24px -8px var(--blue-100)}
.tile .top{display:flex;gap:10px;align-items:flex-start;margin-bottom:8px}
.tile .ic{width:38px;height:38px;border-radius:10px;background:var(--blue-100);
     color:var(--blue-700);font-weight:800;font-size:16px;display:flex;
     align-items:center;justify-content:center;flex-shrink:0}
.tile h3{margin:0;font-size:15.5px;color:var(--blue-900);line-height:1.25}
.tile p{margin:0;color:var(--gray-600);font-size:12.5px;line-height:1.5;flex:1}
.tile .open{margin-top:12px;font-size:12.5px;font-weight:800;color:var(--blue-700)}
.chip{font-size:9.5px;text-transform:uppercase;letter-spacing:.08em;font-weight:800;
     padding:2px 7px;border-radius:6px;white-space:nowrap}
.chip.ok{background:var(--em-100);color:var(--em-800);border:1px solid var(--em-300)}
.chip.bad{background:var(--red-100);color:var(--red-700);border:1px solid var(--red-300)}
.chip.busy{background:var(--am-100);color:var(--am-800);border:1px solid var(--am-300)}
/* detail page */
.card{background:#fff;border:1px solid var(--gray-200);border-radius:14px;
     padding:20px;margin-bottom:16px}
.card h2{font-size:12px;text-transform:uppercase;letter-spacing:.1em;
     color:var(--gray-400);margin:0 0 12px;font-weight:800}
.wow{background:var(--blue-50);border:1px solid var(--blue-100);border-radius:12px;
     padding:14px 16px;color:var(--blue-900);font-size:13.5px;line-height:1.55;
     margin:0 0 18px}
.does{margin:0 0 14px;font-size:13.5px;line-height:1.55;color:var(--gray-900)}
.steps{margin:0;padding-left:0;list-style:none;counter-reset:s;
     display:flex;flex-direction:column;gap:10px}
.steps li{position:relative;padding-left:34px;font-size:13px;line-height:1.5;
     color:var(--gray-600);counter-increment:s}
.steps li::before{content:counter(s);position:absolute;left:0;top:-1px;width:22px;
     height:22px;border-radius:50%;background:var(--blue-100);color:var(--blue-700);
     font-weight:800;font-size:11px;display:flex;align-items:center;justify-content:center}
.video{aspect-ratio:16/9;border-radius:10px;overflow:hidden;background:var(--gray-100);
     display:flex;align-items:center;justify-content:center;color:var(--gray-400);
     font-weight:600;border:1px dashed var(--gray-200)}
.video iframe{width:100%;height:100%;border:0}
.assets{display:flex;flex-direction:column;gap:8px}
.asset{display:flex;align-items:center;gap:10px;padding:10px 12px;border:1px solid
     var(--gray-200);border-radius:10px;text-decoration:none;color:inherit}
.asset:hover{border-color:var(--blue-300);background:var(--blue-50)}
.asset .k{width:28px;height:28px;border-radius:8px;background:var(--gray-100);
     display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0}
.asset .l{font-weight:700;font-size:13px;color:var(--gray-900)}
.asset .s{font-size:11.5px;color:var(--gray-500)}
.resetrow{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.resetbtn{background:#fff;border:1px solid var(--red-300);color:var(--red-700);
     border-radius:9px;padding:9px 16px;font-size:13px;font-weight:700;cursor:pointer}
.resetbtn:hover{background:var(--red-100)} .resetbtn:disabled{opacity:.5;cursor:wait}
.note{font-size:12px;color:var(--gray-500)}
.runbar{font-size:12.5px;color:var(--am-800);background:var(--am-100);
     border:1px solid var(--am-300);border-radius:8px;padding:6px 10px;display:none}
.about{margin-top:26px;font-size:11.5px;color:var(--gray-400);line-height:1.5;
     border-top:1px solid var(--gray-200);padding-top:14px;max-width:760px}
.back{font-size:12.5px;text-decoration:none;font-weight:700;display:inline-block;
     margin-bottom:10px}
@media (max-width:760px){.layout{flex-direction:column}.side{width:100%;
     flex-direction:row;flex-wrap:wrap;align-items:center}.side .spacer{display:none}
     .main{padding:22px 18px}}
</style></head><body>
<div class="layout">
  <nav class="side">
    <div class="brand"><div class="mark">B</div>
      <div><div class="t1" id="entity">Bricksurance SE</div>
      <div class="t2">Excel Accelerator</div></div></div>
    <a class="nav" href="#/" data-r="/"><span class="no">⌂</span>Overview</a>
    <div class="navlbl">The four demos</div>
    <div id="sidenav"></div>
    <div class="spacer"></div>
    <div class="runbar" id="runbar"></div>
    <button class="resetall" onclick="doReset('all', this)">↺ Reset everything</button>
    <div class="foot">
      <a href="#" id="doclink" target="_blank">📄 Full demo guide</a>
      <a href="#" id="repolink" target="_blank">⌥ GitHub repository</a>
    </div>
  </nav>
  <main class="main" id="main"></main>
</div>
<script>
const DATA = __DATA__;
let STATUS = null;

const $  = (s) => document.querySelector(s);
const esc = (t) => t.replace(/&/g,'&amp;').replace(/</g,'&lt;');

function ytEmbed(u){
  const m = u.match(/(?:youtu\\.be\\/|v=)([\\w-]{6,})/);
  return m ? `https://www.youtube.com/embed/${m[1]}` : u;
}
function chipFor(id){
  if (!STATUS) return '<span class="chip busy">checking…</span>';
  const s = STATUS.scenarios.find(x => x.id === id);
  if (!s) return '';
  if (s.busy) return '<span class="chip busy">resetting…</span>';
  if (!s.ok) return `<span class="chip bad">${esc(s.detail)}</span>`;
  return `<span class="chip ok">${s.pending ? 'ready · canvas pending' : 'ready'}</span>`;
}
function nav(){
  $('#sidenav').innerHTML = DATA.scenarios.map(sc =>
    `<a class="nav" href="#/${sc.id}" data-r="/${sc.id}">
       <span class="no">${sc.n}</span>${esc(sc.title)}</a>`).join('');
}
function landing(){
  return `
    <div class="eyebrow">Actuarial Excel Accelerator</div>
    <h1>Escaping the spreadsheet estate</h1>
    <p class="sub">Four migrations off the Excel estate an insurance company actually
      runs on — each one a complete, self-runnable demo with a recording, the assets
      and a reset button. Pick a scenario.</p>
    <div class="grid">` +
    DATA.scenarios.map(sc => `
      <a class="tile" href="#/${sc.id}">
        <div class="top"><div class="ic">${sc.n}</div>
          <h3>${esc(sc.title)}</h3>
          <span style="margin-left:auto" id="chip-${sc.id}">${chipFor(sc.id)}</span></div>
        <p>${esc(sc.strap)}</p>
        <div class="open">Open →</div>
      </a>`).join('') + `
    </div>
    <div class="about"><b>About this demo.</b> A Databricks Field Engineering
      demonstration for ${esc(DATA.entity)} — a fictional composite insurer. All data
      is synthetic; no customer data is used.</div>`;
}
function detail(sc){
  const video = sc.youtube
    ? `<div class="video"><iframe src="${ytEmbed(sc.youtube)}" allowfullscreen
         title="recording"></iframe></div>`
    : `<div class="video">▶ Recording coming soon</div>`;
  const live = (STATUS?.scenarios.find(x => x.id === sc.id)?.live || []).map(l => `
      <a class="asset" href="${l.href}" target="_blank">
        <div class="k">⚡</div><div><div class="l">${esc(l.label)}</div>
        <div class="s">Live in this workspace</div></div></a>`).join('');
  const host = STATUS ? STATUS.host : '';
  return `
    <a class="back" href="#/">← All scenarios</a>
    <div class="eyebrow">Use case ${sc.n}</div>
    <h1>${esc(sc.title)} <span id="chip-${sc.id}" style="vertical-align:4px">${chipFor(sc.id)}</span></h1>
    <p class="sub">${esc(sc.strap)}</p>
    <p class="wow">${esc(sc.wow)}</p>
    <div class="card"><h2>What this demo does</h2>
      <p class="does">${esc(sc.does)}</p>
      <ol class="steps">${sc.steps.map(t => `<li>${esc(t)}</li>`).join('')}</ol>
    </div>
    <div class="card"><h2>Recording</h2>${video}</div>
    <div class="card"><h2>Assets</h2><div class="assets">
      <a class="asset" href="${host}/#workspace${sc.folder}" target="_blank">
        <div class="k">📓</div><div><div class="l">Open the notebooks</div>
        <div class="s">${esc(sc.folder)}</div></div></a>
      <a class="asset" href="${DATA.docUrl}?tab=${sc.doc_tab}" target="_blank">
        <div class="k">📄</div><div><div class="l">Step-by-step walkthrough</div>
        <div class="s">Demo guide — use case ${sc.n} tab</div></div></a>
      ${live}
    </div></div>
    <div class="card"><h2>Reset</h2>
      <div class="resetrow">
        <button class="resetbtn" onclick="doReset('${sc.id}', this)">↺ Reset this scenario</button>
        <span class="note">${esc(sc.reset_note)} Brings the demo back to its original
          state if anything was changed or broken.</span>
      </div></div>`;
}
function render(){
  const r = location.hash.replace(/^#/, '') || '/';
  document.querySelectorAll('.nav').forEach(a =>
    a.classList.toggle('active', a.dataset.r === r));
  const sc = DATA.scenarios.find(x => '/' + x.id === r);
  $('#main').innerHTML = sc ? detail(sc) : landing();
}
async function loadStatus(refresh){
  try{
    const res = await fetch('/api/status' + (refresh ? '?refresh=true' : ''));
    STATUS = await res.json();
  }catch(e){ STATUS = null; }
  render();
}
async function pollRuns(){
  try{
    const res = await fetch('/api/reset_status'); const s = await res.json();
    const bar = $('#runbar');
    if (s.active && s.active.length){
      bar.style.display = 'block';
      bar.innerHTML = `⏳ reset running — <a target="_blank" href="${s.active[0].url}">watch the job</a>`;
      if (STATUS) STATUS.scenarios.forEach(x => x.busy = true);
      render();
      setTimeout(pollRuns, 15000);
    } else {
      bar.style.display = 'none';
      if (STATUS && STATUS.scenarios.some(x => x.busy)) loadStatus(true);
    }
  }catch(e){}
}
async function doReset(sc, btn){
  if (!confirm('Reset ' + (sc === 'all' ? 'ALL scenarios' : sc) +
               ' back to the original state?')) return;
  btn.disabled = true;
  try{
    const r = await fetch('/api/reset/' + sc, {method: 'POST'});
    if (!r.ok) alert((await r.json()).detail || 'reset failed');
    else pollRuns();
  } finally { btn.disabled = false; }
}
$('#entity').textContent = DATA.entity;
$('#doclink').href = DATA.docUrl;
$('#repolink').href = DATA.repoUrl;
window.addEventListener('hashchange', render);
nav(); render(); loadStatus(false); pollRuns();
</script></body></html>"""
