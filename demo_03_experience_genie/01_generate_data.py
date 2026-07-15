# Databricks notebook source
# MAGIC %md
# MAGIC # Demo 3 · Step 1 (Land) — Generate the source CSVs
# MAGIC
# MAGIC **Recipe step: Land.** An actuary doesn't start from a database — they
# MAGIC start from a *file export*. This notebook fabricates the two extracts a
# MAGIC pricing/reserving actuary pulls every month and drops into a folder, plus
# MAGIC the little VLOOKUP reference they keep on the side:
# MAGIC
# MAGIC | File | What it is | Rows |
# MAGIC |---|---|---|
# MAGIC | `claims_transactions.csv` | Every claim movement (reserve / payment / recovery) | ~800k |
# MAGIC | `premium_exposure.csv` | Earned premium + exposure by segment × month | ~8.4k |
# MAGIC | `segment_map.csv` | Policy-segment code → line of business / region / channel | 100 |
# MAGIC
# MAGIC The full book spans **accident years 2019–2025**, **5 lines of business**,
# MAGIC **5 regions**, **4 distribution channels** — a multi-year book that Excel
# MAGIC *physically cannot* pivot (it grinds well before this and tops out at
# MAGIC ~1.05M rows on a single sheet). That ceiling is the whole point.
# MAGIC
# MAGIC The data is **fully synthetic** but not random noise — three signals are
# MAGIC deliberately baked in so the demo *reveals* something instead of just
# MAGIC rendering charts:
# MAGIC
# MAGIC 1. **Motor 2022–2023 deteriorating** — claims inflation pushes the loss
# MAGIC    ratio from ~70% toward ~95%+.
# MAGIC 2. **A windstorm cat event** — a cluster of large Home / Commercial Property
# MAGIC    losses in **Scotland, Q1 2023** that spikes that region.
# MAGIC 3. **The Aggregator channel runs hot** — structurally ~12pts worse loss
# MAGIC    ratio than Broker/Direct across every line.
# MAGIC
# MAGIC Files are written to the `exp_landing` Volume created in `00_setup`.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_dev_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
dbutils.widgets.text("exp_volume_name", "exp_landing")
dbutils.widgets.text("seed", "42")

catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
volume = dbutils.widgets.get("exp_volume_name")
seed = int(dbutils.widgets.get("seed"))

vol_path = f"/Volumes/{catalog}/{schema}/{volume}"
print(f"Target volume: {vol_path}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Reference dimensions — the segment map (the VLOOKUP table)

# COMMAND ----------

import numpy as np
import pandas as pd

rng = np.random.default_rng(seed)

LOBS = ["Motor", "Home", "CommercialProperty", "Liability", "Marine"]
REGIONS = ["London", "South", "Midlands", "North", "Scotland"]
CHANNELS = ["Broker", "Direct", "Aggregator", "Partnership"]

LOB3 = {"Motor": "MOT", "Home": "HOM", "CommercialProperty": "CPR", "Liability": "LIA", "Marine": "MAR"}
REG3 = {"London": "LON", "South": "STH", "Midlands": "MID", "North": "NTH", "Scotland": "SCO"}
CHN3 = {"Broker": "BRK", "Direct": "DIR", "Aggregator": "AGG", "Partnership": "PTN"}

seg_rows = []
for lob in LOBS:
    for reg in REGIONS:
        for chn in CHANNELS:
            code = f"{LOB3[lob]}-{REG3[reg]}-{CHN3[chn]}"
            seg_rows.append((code, lob, reg, chn))

segment_map = pd.DataFrame(seg_rows, columns=["policy_segment", "line_of_business", "region", "channel"])
print(f"{len(segment_map)} segments")
segment_map.head()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Premium & exposure — earned premium by segment × accident month
# MAGIC
# MAGIC Each line of business gets a base monthly earned premium and a base volume
# MAGIC of business; regions and channels scale it. This is the denominator of
# MAGIC every loss ratio downstream.

# COMMAND ----------

MONTHS = pd.date_range("2019-01-31", "2025-12-31", freq="M")  # month-end, 84 months

# Size of the book. Scales policy volume (and therefore claim counts) without
# touching loss ratios. ~6 lands the full book around 800k transaction rows —
# far beyond what Excel can pivot — while keeping per-policy economics realistic.
BOOK_SCALE = 6

# Relative size of each line of business (Motor is the big personal-lines book)
LOB_SIZE = {"Motor": 1.0, "Home": 0.55, "CommercialProperty": 0.40, "Liability": 0.30, "Marine": 0.18}
# Average annual premium per policy by line (GBP)
LOB_AVG_PREMIUM = {"Motor": 620, "Home": 310, "CommercialProperty": 4200, "Liability": 2800, "Marine": 9500}
REGION_SIZE = {"London": 1.3, "South": 1.1, "Midlands": 1.0, "North": 0.9, "Scotland": 0.6}
CHANNEL_SIZE = {"Broker": 1.0, "Direct": 0.8, "Aggregator": 1.1, "Partnership": 0.5}

prem_rows = []
for _, s in segment_map.iterrows():
    base_policies = (
        9000 * BOOK_SCALE * LOB_SIZE[s.line_of_business]
        * REGION_SIZE[s.region] * CHANNEL_SIZE[s.channel]
    )
    avg_prem = LOB_AVG_PREMIUM[s.line_of_business]
    for m in MONTHS:
        # gentle volume growth ~4%/yr + seasonality + noise
        yrs = (m.year - 2019) + (m.month - 1) / 12.0
        growth = (1.04) ** yrs
        seasonal = 1.0 + 0.06 * np.sin(2 * np.pi * (m.month - 1) / 12.0)
        policies = base_policies / 12.0 * growth * seasonal * rng.normal(1.0, 0.03)
        policies = max(policies, 1.0)
        # earned premium with a small rate-change drift (3%/yr) on top of volume
        rate_drift = (1.03) ** yrs
        earned = policies * (avg_prem / 12.0) * rate_drift * rng.normal(1.0, 0.02)
        prem_rows.append((s.policy_segment, m.date().isoformat(),
                          int(round(policies)), round(earned, 2), round(policies, 2)))

premium = pd.DataFrame(prem_rows, columns=[
    "policy_segment", "earned_month", "policy_count", "earned_premium", "exposure"])
print(f"{len(premium):,} premium rows · total earned £{premium.earned_premium.sum():,.0f}")
premium.head()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Target loss ratios — where the story lives
# MAGIC
# MAGIC For each segment × accident year we pick an *ultimate* loss ratio. The
# MAGIC three baked-in signals are applied here; everything downstream just
# MAGIC realises these targets as individual claims.

# COMMAND ----------

LOB_BASE_LR = {"Motor": 0.70, "Home": 0.62, "CommercialProperty": 0.58,
               "Liability": 0.65, "Marine": 0.60}
CHANNEL_LR_UPLIFT = {"Broker": 0.00, "Direct": -0.02, "Aggregator": 0.12, "Partnership": 0.03}
ACCIDENT_YEARS = list(range(2019, 2026))


def target_loss_ratio(lob, region, channel, ay):
    lr = LOB_BASE_LR[lob] + CHANNEL_LR_UPLIFT[channel]
    # Signal 1: Motor inflation 2022-2023
    if lob == "Motor":
        lr += {2019: 0.0, 2020: -0.04, 2021: 0.01, 2022: 0.12, 2023: 0.20,
               2024: 0.10, 2025: 0.05}.get(ay, 0.0)
    # Signal 2: Scotland windstorm Q1 2023 (property lines)
    if region == "Scotland" and ay == 2023 and lob in ("Home", "CommercialProperty"):
        lr += 0.35
    # general small year-on-year noise
    lr += rng.normal(0.0, 0.015)
    return max(lr, 0.20)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Claims — frequency, severity, and development
# MAGIC
# MAGIC Per segment × accident year we compute target *ultimate* incurred =
# MAGIC `target_LR × earned_premium`, then split it into claims with a
# MAGIC line-specific frequency/severity mix. Each claim then *develops*: an
# MAGIC initial case reserve at report, payments and reserve revisions over a
# MAGIC line-specific tail, occasional recoveries, and a close. Property is
# MAGIC short-tail, Liability is long-tail, Motor in between.

# COMMAND ----------

# Average claim severity by line (GBP) — drives frequency given the incurred target
LOB_SEVERITY = {"Motor": 3200, "Home": 2600, "CommercialProperty": 9000,
                "Liability": 14000, "Marine": 22000}
# Development tail: number of months over which a claim pays out (mean)
LOB_TAIL_M = {"Motor": 14, "Home": 7, "CommercialProperty": 11, "Liability": 40, "Marine": 20}
# Reporting delay mean (days)
LOB_REPORT_LAG = {"Motor": 12, "Home": 9, "CommercialProperty": 25, "Liability": 95, "Marine": 35}
# Share of claims that are "large losses"
LOB_LARGE_P = {"Motor": 0.010, "Home": 0.020, "CommercialProperty": 0.035,
               "Liability": 0.050, "Marine": 0.060}

PERILS = {
    "Motor": ["AD", "TP_Injury", "TP_Damage", "Theft", "Windscreen"],
    "Home": ["Escape_of_Water", "Storm", "Fire", "Theft", "Accidental_Damage"],
    "CommercialProperty": ["Fire", "Storm", "Flood", "BusinessInterruption", "Impact"],
    "Liability": ["EL_Injury", "PL_Injury", "PL_Damage", "ProfIndemnity"],
    "Marine": ["Hull", "Cargo", "Liability", "War"],
}

# Earned premium per segment × accident year (sum of the 12 months in that AY)
premium["_ay"] = pd.to_datetime(premium.earned_month).dt.year
ep_by_seg_ay = premium.groupby(["policy_segment", "_ay"]).earned_premium.sum().to_dict()
seg_lookup = segment_map.set_index("policy_segment")[["line_of_business", "region", "channel"]].to_dict("index")

# COMMAND ----------

def dev_schedule(tail_m, n_pay, is_large, peril_storm):
    """Return sorted dev-month offsets for the payment movements of one claim."""
    if peril_storm:
        # cat / storm claims settle fast and bunched
        offs = rng.integers(0, max(2, int(tail_m * 0.4)) + 1, size=n_pay)
    else:
        # right-skewed across the tail; large losses develop slower
        scale = tail_m * (1.4 if is_large else 1.0) / 2.5
        offs = np.abs(rng.gamma(shape=2.0, scale=scale, size=n_pay)).astype(int)
    return np.sort(np.clip(offs, 0, 120))


rows = []
claim_seq = 0
GEN_END = pd.Timestamp("2025-12-31")  # valuation / extract date

for code, info in seg_lookup.items():
    lob, region, channel = info["line_of_business"], info["region"], info["channel"]
    sev = LOB_SEVERITY[lob]
    tail = LOB_TAIL_M[lob]
    large_p = LOB_LARGE_P[lob]
    perils = PERILS[lob]
    for ay in ACCIDENT_YEARS:
        ep = ep_by_seg_ay.get((code, ay), 0.0)
        if ep <= 0:
            continue
        lr = target_loss_ratio(lob, region, channel, ay)
        target_incurred = ep * lr
        # Calibrate the claim count to the EXPECTED realised severity, not the
        # nominal `sev`, so total incurred lands on target_incurred (= target LR).
        # Expected severity inflates for two reasons: the lognormal mean is
        # exp(sigma^2/2) above its median, and a fraction `large_p` of claims are
        # large losses ~19x. Without this the loss ratio drifts well above target.
        expected_sev = sev * 1.2776 * (1.0 + large_p * (19.0 - 1.0))
        n_claims = max(int(round(target_incurred / expected_sev)), 0)
        if n_claims == 0:
            continue
        is_storm_seg = (region == "Scotland" and ay == 2023 and lob in ("Home", "CommercialProperty"))
        for _ in range(n_claims):
            claim_seq += 1
            claim_id = f"CLM-{claim_seq:07d}"
            is_large = rng.random() < (large_p * (3 if is_storm_seg else 1))
            # accident date uniformly in the accident year
            doy = rng.integers(0, 365)
            if is_storm_seg:
                doy = rng.integers(0, 90)  # Q1 storm window
            acc_date = pd.Timestamp(f"{ay}-01-01") + pd.Timedelta(days=int(doy))
            # reporting delay
            lag = max(int(rng.exponential(LOB_REPORT_LAG[lob])), 0)
            rep_date = acc_date + pd.Timedelta(days=lag)
            if rep_date > GEN_END:
                continue  # not yet reported as of the extract date
            # ultimate incurred for this claim (lognormal around severity)
            mult = 1.0
            if is_large:
                mult = rng.uniform(8, 30)
            ult = max(rng.lognormal(mean=np.log(sev), sigma=0.7) * mult, 50.0)

            peril = ("Storm" if is_storm_seg else rng.choice(perils))
            # number of payment movements
            n_pay = int(np.clip(rng.poisson(2.2 if not is_large else 4.5), 1, 12))
            offs = dev_schedule(tail, n_pay, is_large, is_storm_seg)
            # split ultimate into payment increments (dirichlet)
            weights = rng.dirichlet(np.ones(n_pay) * 1.3)
            pay_incrs = ult * weights

            # ---- initial case reserve at report (RESERVE_CHANGE +) ----
            reserve_balance = ult * rng.uniform(0.85, 1.25)  # initial estimate, imperfect
            rows.append((claim_id, code, peril, acc_date.date().isoformat(),
                         rep_date.date().isoformat(), rep_date.date().isoformat(),
                         0, "RESERVE_CHANGE", round(reserve_balance, 2), bool(is_large)))

            paid_cum = 0.0
            last_txn = rep_date
            for k in range(n_pay):
                txn_date = rep_date + pd.Timedelta(days=int(offs[k] * 30))
                if txn_date > GEN_END:
                    break  # not yet developed as of the extract date
                dev_m = (txn_date.year - acc_date.year) * 12 + (txn_date.month - acc_date.month)
                pay = pay_incrs[k]
                paid_cum += pay
                rows.append((claim_id, code, peril, acc_date.date().isoformat(),
                             rep_date.date().isoformat(), txn_date.date().isoformat(),
                             int(dev_m), "PAYMENT", round(pay, 2), bool(is_large)))
                # reserve drawn down toward remaining estimate
                remaining = max(ult - paid_cum, 0.0)
                resv_change = remaining - reserve_balance
                reserve_balance = remaining
                if abs(resv_change) > 1:
                    rows.append((claim_id, code, peril, acc_date.date().isoformat(),
                                 rep_date.date().isoformat(), txn_date.date().isoformat(),
                                 int(dev_m), "RESERVE_CHANGE", round(resv_change, 2), bool(is_large)))
                last_txn = txn_date
                # occasional recovery (salvage/subrogation) on property & motor
                if lob in ("Motor", "Home", "CommercialProperty", "Marine") and rng.random() < 0.06:
                    rec = -pay * rng.uniform(0.05, 0.30)
                    rows.append((claim_id, code, peril, acc_date.date().isoformat(),
                                 rep_date.date().isoformat(), txn_date.date().isoformat(),
                                 int(dev_m), "RECOVERY", round(rec, 2), bool(is_large)))

            # ---- close the claim: zero out the case reserve if fully developed ----
            close = last_txn + pd.Timedelta(days=int(rng.uniform(15, 75)))
            if close <= GEN_END and reserve_balance > 1 and rng.random() < 0.8:
                dev_m = (close.year - acc_date.year) * 12 + (close.month - acc_date.month)
                rows.append((claim_id, code, peril, acc_date.date().isoformat(),
                             rep_date.date().isoformat(), close.date().isoformat(),
                             int(dev_m), "RESERVE_CHANGE", round(-reserve_balance, 2), bool(is_large)))

print(f"Generated {len(rows):,} transaction rows across {claim_seq:,} claims")

# COMMAND ----------

claims = pd.DataFrame(rows, columns=[
    "claim_id", "policy_segment", "peril", "accident_date", "report_date",
    "transaction_date", "dev_month", "transaction_type", "transaction_amount",
    "large_loss_flag"])
print(f"{len(claims):,} rows")
display(claims.head(20))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Write the three CSVs to the Volume
# MAGIC
# MAGIC Written via the driver's local `/tmp` then copied into the Volume — the
# MAGIC robust pattern on serverless. The result is three plain `.csv` files an
# MAGIC actuary would recognise as "the export".

# COMMAND ----------

import shutil, os

local_dir = "/tmp/exp_gen"
os.makedirs(local_dir, exist_ok=True)

to_write = {
    "segment_map.csv": segment_map,
    "premium_exposure.csv": premium.drop(columns=["_ay"]),
    "claims_transactions.csv": claims,
}

for fname, df in to_write.items():
    lp = f"{local_dir}/{fname}"
    df.to_csv(lp, index=False)
    dst = f"{vol_path}/{fname}"
    shutil.copyfile(lp, dst)
    size_mb = os.path.getsize(lp) / 1e6
    print(f"✓ {fname:28s} {len(df):>10,} rows  {size_mb:6.1f} MB → {dst}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The Excel slice — a piece small enough for the "before" workbook
# MAGIC
# MAGIC The full book can't live in Excel. But to *prove parity* against the legacy
# MAGIC workbook we carve out one slice an actuary could realistically pivot by
# MAGIC hand — **Motor · London · accident year 2024** (~20k transaction rows). It
# MAGIC is an exact filter of the data above, so the Databricks gold table must
# MAGIC reproduce its totals (that's `05_parity.py`). These two files feed
# MAGIC `excel/build_excel_data.py`, which builds `Experience_Monitoring.xlsx`.

# COMMAND ----------

claims_slice = claims.merge(segment_map, on="policy_segment")
claims_slice = claims_slice[
    (claims_slice.line_of_business == "Motor")
    & (claims_slice.region == "London")
    & (pd.to_datetime(claims_slice.accident_date).dt.year == 2024)
].copy()

premium_slice = premium.merge(segment_map, on="policy_segment")
premium_slice = premium_slice[
    (premium_slice.line_of_business == "Motor")
    & (premium_slice.region == "London")
    & (premium_slice._ay == 2024)
].drop(columns=["_ay"]).copy()

for fname, df in {"experience_excel_claims.csv": claims_slice,
                  "experience_excel_premium.csv": premium_slice}.items():
    lp = f"{local_dir}/{fname}"
    df.to_csv(lp, index=False)
    shutil.copyfile(lp, f"{vol_path}/{fname}")
    print(f"✓ {fname:30s} {len(df):>8,} rows → {vol_path}/{fname}")

print("\nDownload these two slice files to build the Excel workbook locally:")
print(f"  databricks fs cp dbfs:{vol_path}/experience_excel_claims.csv  demo_03_experience_genie/data/")
print(f"  databricks fs cp dbfs:{vol_path}/experience_excel_premium.csv demo_03_experience_genie/data/")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Quick reality check on the baked-in signals

# COMMAND ----------

chk = claims.merge(segment_map, on="policy_segment")
chk["ay"] = pd.to_datetime(chk.accident_date).dt.year
chk["paid"] = np.where(chk.transaction_type.isin(["PAYMENT", "RECOVERY"]), chk.transaction_amount, 0.0)
chk["osr"] = np.where(chk.transaction_type == "RESERVE_CHANGE", chk.transaction_amount, 0.0)
inc = chk.groupby(["line_of_business", "ay"]).apply(
    lambda g: (g.paid.sum() + g.osr.sum())).rename("incurred").reset_index()
ep = premium.copy()
ep = ep.merge(segment_map, on="policy_segment")
ep["ay"] = pd.to_datetime(ep.earned_month).dt.year
epg = ep.groupby(["line_of_business", "ay"]).earned_premium.sum().reset_index()
lr = inc.merge(epg, on=["line_of_business", "ay"])
lr["loss_ratio"] = (lr.incurred / lr.earned_premium).round(3)
print("Motor loss ratio by accident year (expect 2022-23 to climb):")
print(lr[lr.line_of_business == "Motor"][["ay", "loss_ratio"]].to_string(index=False))

# COMMAND ----------

print("Land step complete. Next: 02_bronze.py")
