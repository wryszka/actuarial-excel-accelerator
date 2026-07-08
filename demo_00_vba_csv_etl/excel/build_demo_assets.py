"""Build demo 0's source assets: the messy vendor CSVs, the VBA's expected
output (a Python oracle that mirrors the VBA logic line for line), and the
Excel workbook shell.

The bordereau CSVs are what the actuary "downloads from the TPA" each month.
They are deliberately dirty in ways old VBA accumulates rules for:
  - loss dates in three formats (dd/mm/yyyy, yyyy-mm-dd, dd-Mon-yy)
    plus a few unusable ones (TBC, blank, impossible dates)
  - money as "£1234.56", "1234.56", "-", "" and "(123.45)" for negatives
  - status codes with dirt: O / RO / C / CWP plus "OPEN", "o", "C ", "closed"
  - ~600 exact duplicate rows per month (vendor extract double-fires)

The oracle applies EXACTLY the rules in ClaimsBordereauETL.bas:
  keep first occurrence per ClaimRef → drop rows whose loss date won't parse
  (silently!) → blank unusable report dates → strip £/() → map status →
  incurred = round(paid + outstanding, 2) → drop the Handler column.

Run:  uv run --with pandas --with openpyxl python build_demo_assets.py
Outputs are committed so the repo is self-contained and deterministic.
"""
import csv
import os
import random
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "data"))
os.makedirs(DATA, exist_ok=True)

MONTHS_3 = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTH_NO = {m.upper(): i + 1 for i, m in enumerate(MONTHS_3)}

PERILS = ["AD", "TPPD", "TPBI", "TH", "WS", "FI"]
PERIL_W = [0.35, 0.25, 0.10, 0.12, 0.13, 0.05]
REGIONS = ["London", "South", "Midlands", "North", "Scotland"]
REGION_W = [0.28, 0.24, 0.20, 0.18, 0.10]
STATUS_POOL = [("C", 0.42), ("O", 0.22), ("CWP", 0.09), ("RO", 0.05),
               ("closed", 0.08), ("OPEN", 0.06), ("o", 0.03), ("C ", 0.05)]
BAD_LOSS_DATES = ["TBC", "", "31/13/2025", "00/01/2025", "31/04/2025"]

N_BASE = 44_400          # unique rows per month
N_DUPES = 600            # exact duplicates appended adjacent
BAD_DATE_RATE = 0.0045   # ~200 rows/month the VBA silently drops


def fmt_date(d: date, style: int) -> str:
    if style == 0:
        return d.strftime("%d/%m/%Y")
    if style == 1:
        return d.strftime("%Y-%m-%d")
    return f"{d.day:02d}-{MONTHS_3[d.month - 1]}-{d.year % 100:02d}"


def fmt_amount(value: float, rng: random.Random) -> str:
    """Format a 2dp amount the way the vendor file mangles it."""
    if value < 0:
        return f"({abs(value):.2f})"
    r = rng.random()
    if value == 0:
        return rng.choice(["-", "", "0.00"])
    if r < 0.60:
        return f"£{value:.2f}"
    return f"{value:.2f}"


def gen_month(year: int, month: int, seed: int):
    rng = random.Random(seed)
    month_end = date(year, month, 28)
    while (month_end + timedelta(days=1)).month == month:
        month_end += timedelta(days=1)

    rows = []
    for i in range(1, N_BASE + 1):
        claim_ref = f"BRD-{year}M{month:02d}-{i:06d}"
        policy_no = f"POL-{rng.randint(1_000_000, 9_999_999)}"
        # long-tail: losses up to ~700 days back, skewed recent
        back = int(rng.betavariate(1.2, 3.0) * 700)
        loss = month_end - timedelta(days=back)
        report = loss + timedelta(days=int(rng.expovariate(1 / 12)))
        if report > month_end:
            report = month_end

        if rng.random() < BAD_DATE_RATE:
            loss_s = rng.choice(BAD_LOSS_DATES)
        else:
            loss_s = fmt_date(loss, rng.choices([0, 1, 2], weights=[0.70, 0.20, 0.10])[0])
        report_s = "" if rng.random() < 0.003 else report.strftime("%d/%m/%Y")

        status = rng.choices([s for s, _ in STATUS_POOL],
                             weights=[w for _, w in STATUS_POOL])[0]
        closedish = status.strip().upper() in ("C", "CLOSED", "CWP")

        sev = round(rng.lognormvariate(7.4, 1.1), 2)  # ~£1.6k median
        if status.strip().upper() == "CWP":
            paid_v, outst_v = 0.0, 0.0
        elif closedish:
            paid_v, outst_v = sev, 0.0
        else:
            frac = rng.uniform(0.0, 0.7)
            paid_v = round(sev * frac, 2)
            outst_v = round(sev - paid_v, 2)
        if rng.random() < 0.01:  # salvage/subrogation recovery
            paid_v = round(-abs(sev) * rng.uniform(0.05, 0.3), 2)
            outst_v = 0.0

        rows.append([
            claim_ref, policy_no, loss_s, report_s, status,
            rng.choices(PERILS, weights=PERIL_W)[0],
            rng.choices(REGIONS, weights=REGION_W)[0],
            "".join(rng.choices("ABCDEFGHJKLMNPRSTW", k=3)),
            fmt_amount(paid_v, rng), fmt_amount(outst_v, rng),
        ])

    # exact duplicate rows, inserted adjacent to the original
    for idx in sorted(rng.sample(range(len(rows)), N_DUPES), reverse=True):
        rows.insert(idx + 1, list(rows[idx]))
    return rows


# ---------------------------------------------------------------------------
# The oracle — EXACTLY the VBA's rules (see ClaimsBordereauETL.bas)
# ---------------------------------------------------------------------------

def parse_date_iso(s: str) -> str:
    s = s.strip()
    if not s:
        return ""
    try:
        if "/" in s:
            p = s.split("/")
            if len(p) != 3:
                return ""
            d, m, y = int(p[0]), int(p[1]), int(p[2])
        elif "-" in s:
            p = s.split("-")
            if len(p) != 3:
                return ""
            if len(p[0]) == 4:
                y, m, d = int(p[0]), int(p[1]), int(p[2])
            else:
                d = int(p[0])
                m = MONTH_NO.get(p[1][:3].upper(), 0)
                y = 2000 + int(p[2])
                if m == 0:
                    return ""
        else:
            return ""
        if not (1 <= m <= 12 and 1 <= d <= 31):
            return ""
        return date(y, m, d).isoformat()   # raises on 31/04 etc., like DateSerial check
    except (ValueError, TypeError):
        return ""


def parse_amount(s: str) -> float:
    t = s.strip()
    if t in ("", "-"):
        return 0.0
    neg = t.startswith("(") and t.endswith(")")
    if neg:
        t = t[1:-1]
    t = t.replace("£", "").replace(",", "")
    try:
        v = float(t)
    except ValueError:
        v = 0.0
    return -v if neg else v


def map_status(s: str) -> str:
    u = s.strip().upper()
    return {"O": "Open", "OPEN": "Open", "RO": "Reopened", "REOPENED": "Reopened",
            "C": "Closed", "CLOSED": "Closed", "CWP": "ClosedWithoutPayment"}.get(u, "UNKNOWN")


def run_oracle(rows):
    seen, out = set(), []
    for r in rows:
        ref = r[0].strip()
        if ref in seen:
            continue
        seen.add(ref)
        loss = parse_date_iso(r[2])
        if not loss:
            continue                      # the silent drop
        paid = parse_amount(r[8])
        outst = parse_amount(r[9])
        out.append([ref, r[1].strip(), loss, parse_date_iso(r[3]),
                    map_status(r[4]), r[5].strip(), r[6].strip(),
                    f"{paid:.2f}", f"{outst:.2f}", f"{round(paid + outst, 2):.2f}"])
    return out


IN_HEADER = ["ClaimRef", "PolicyNo", "LossDate", "ReportDate", "Status",
             "PerilCode", "Region", "Handler", "PaidGBP", "OutstandingGBP"]
OUT_HEADER = ["claim_ref", "policy_no", "loss_date", "report_date", "status",
              "peril_code", "region", "paid_gbp", "outstanding_gbp", "incurred_gbp"]


def write_csv(path, header, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"✓ {path}  ({len(rows):,} rows)")


for (y, m, seed) in [(2025, 11, 411), (2025, 12, 412)]:
    rows = gen_month(y, m, seed)
    write_csv(os.path.join(DATA, f"bordereau_{y}_{m:02d}.csv"), IN_HEADER, rows)
    oracle = run_oracle(rows)
    write_csv(os.path.join(DATA, f"expected_output_{y}_{m:02d}.csv"), OUT_HEADER, oracle)
    dropped = len({r[0] for r in rows}) - len(oracle)
    print(f"   month {y}-{m:02d}: {len(rows):,} landed rows, {len(rows) - len({tuple(r) for r in rows})} dupes, "
          f"{dropped} rows silently dropped by the VBA (bad loss dates)")

# ---------------------------------------------------------------------------
# Workbook shell (import the .bas into this and save as .xlsm)
# ---------------------------------------------------------------------------
from openpyxl import Workbook
from openpyxl.styles import Font

wb = Workbook()
ws = wb.active
ws.title = "Instructions"
ws["A1"] = "Bordereau ETL — legacy workbook (demo fixture)"
ws["A1"].font = Font(bold=True, size=14)
lines = [
    "",
    "This is the 'before' artefact for demo 0. One-time setup:",
    "  1. Open this file in Excel.",
    "  2. Tools → Macro → Visual Basic Editor (⌥F11).",
    "  3. File → Import File… → select ClaimsBordereauETL.bas (next to this file).",
    "  4. Save As → Excel Macro-Enabled Workbook → Bordereau_ETL.xlsm.",
    "     (.xlsm files are kept local; they are excluded from git/bundle sync.)",
    "",
    "To run the monthly process (what the actuary does):",
    "  1. Run macro RunMonthlyETL.",
    "  2. Pick the month's bordereau CSV (e.g. data/bordereau_2025_11.csv).",
    "  3. The macro fills the Raw and Standardised tabs and writes",
    "     <input>_STANDARDISED.csv next to the input file.",
    "  4. That output is what gets uploaded 'into the pricing system'.",
    "",
    "About this demo: all data is synthetic; no customer data is used.",
]
for i, line in enumerate(lines, start=2):
    ws.cell(row=i, column=1, value=line)
ws.column_dimensions["A"].width = 95
out = os.path.join(HERE, "Bordereau_ETL.xlsx")
wb.save(out)
print(f"✓ {out}")
