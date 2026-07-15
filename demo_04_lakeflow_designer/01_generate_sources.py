# Databricks notebook source
# MAGIC %md
# MAGIC # Use Case 4 · Step 1 — generate the canvas sources (standalone)
# MAGIC
# MAGIC Builds everything this use case needs, depending on **nothing else**:
# MAGIC
# MAGIC | Asset (`dsg_` prefix) | What it is |
# MAGIC |---|---|
# MAGIC | `dsg_claims_src` | claim-grain source, only `policy_segment` — so the lookup join is a real canvas step (the VLOOKUP) |
# MAGIC | `dsg_premium_src` | earned premium by segment × accident year — the second branch of the blend |
# MAGIC | `dsg_segment` | the segment → line-of-business / region / channel lookup |
# MAGIC | `dsg_benchmark` | the answer the coded pipeline would produce (LOB × accident year: earned_premium, incurred, loss_ratio) — `02_parity` proves the canvas matches this |
# MAGIC | `claims_extract.csv` | in the `dsg_landing` volume — the optional drag-a-file-onto-the-canvas beat |
# MAGIC
# MAGIC Synthetic, deterministic (fixed seed). Small enough to build in ~1 min,
# MAGIC big enough to be real (~40k claims). Carries one baked-in signal so the
# MAGIC result *shows* something: Motor loss ratio climbs across 2022–2023.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_serverless_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
dbutils.widgets.text("dsg_volume_name", "dsg_landing")
dbutils.widgets.text("seed", "404")

catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
volume = dbutils.widgets.get("dsg_volume_name")
seed = int(dbutils.widgets.get("seed"))
fqn = f"{catalog}.{schema}"
vol_path = f"/Volumes/{catalog}/{schema}/{volume}"

# COMMAND ----------

import numpy as np
import pandas as pd

rng = np.random.default_rng(seed)

LOBS = ["Motor", "Home", "CommercialProperty", "Liability", "Marine"]
REGIONS = ["London", "South", "Midlands", "North", "Scotland"]
CHANNELS = ["Broker", "Direct", "Aggregator", "Partnership"]
L3 = {"Motor": "MOT", "Home": "HOM", "CommercialProperty": "CPR", "Liability": "LIA", "Marine": "MAR"}
R3 = {"London": "LON", "South": "STH", "Midlands": "MID", "North": "NTH", "Scotland": "SCO"}
C3 = {"Broker": "BRK", "Direct": "DIR", "Aggregator": "AGG", "Partnership": "PTN"}

seg_rows = [(f"{L3[l]}-{R3[r]}-{C3[c]}", l, r, c)
            for l in LOBS for r in REGIONS for c in CHANNELS]
segment = pd.DataFrame(seg_rows, columns=["policy_segment", "line_of_business", "region", "channel"])
AY = list(range(2021, 2026))

LOB_SIZE = {"Motor": 1.0, "Home": 0.55, "CommercialProperty": 0.4, "Liability": 0.3, "Marine": 0.18}
LOB_PREM = {"Motor": 620, "Home": 310, "CommercialProperty": 4200, "Liability": 2800, "Marine": 9500}
LOB_SEV = {"Motor": 3200, "Home": 2600, "CommercialProperty": 9000, "Liability": 14000, "Marine": 22000}
LOB_BASE_LR = {"Motor": 0.70, "Home": 0.62, "CommercialProperty": 0.58, "Liability": 0.65, "Marine": 0.60}
CH_LR = {"Broker": 0.0, "Direct": -0.02, "Aggregator": 0.12, "Partnership": 0.03}
REG_SIZE = {"London": 1.3, "South": 1.1, "Midlands": 1.0, "North": 0.9, "Scotland": 0.6}
CH_SIZE = {"Broker": 1.0, "Direct": 0.8, "Aggregator": 1.1, "Partnership": 0.5}


def target_lr(lob, ch, ay):
    lr = LOB_BASE_LR[lob] + CH_LR[ch]
    if lob == "Motor":
        lr += {2021: 0.01, 2022: 0.12, 2023: 0.20, 2024: 0.10, 2025: 0.05}.get(ay, 0.0)
    return max(lr + rng.normal(0, 0.01), 0.2)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Premium (segment × accident year) and the benchmark loss ratios

# COMMAND ----------

prem_rows, claim_rows, bench = [], [], []
claim_seq = 0
for _, s in segment.iterrows():
    lob, reg, ch = s.line_of_business, s.region, s.channel
    for ay in AY:
        ep = (900 * LOB_SIZE[lob] * REG_SIZE[reg] * CH_SIZE[ch]
              * (LOB_PREM[lob]) * rng.normal(1.0, 0.02))
        ep = round(max(ep, 1000.0), 2)
        prem_rows.append((s.policy_segment, ay, ep))
        lr = target_lr(lob, ch, ay)
        target_incurred = ep * lr
        # calibrate to EXPECTED severity (lognormal mean = median·exp(sigma^2/2),
        # sigma=0.6) so realised loss ratio lands on target, not ~20% above
        expected_sev = LOB_SEV[lob] * 1.1972
        n = max(int(round(target_incurred / expected_sev)), 0)
        seg_incurred = 0.0
        for _ in range(n):
            claim_seq += 1
            inc = round(max(rng.lognormal(np.log(LOB_SEV[lob]), 0.6), 50.0), 2)
            seg_incurred += inc
            doy = int(rng.integers(0, 365))
            acc = pd.Timestamp(f"{ay}-01-01") + pd.Timedelta(days=doy)
            paid = round(inc * rng.uniform(0.4, 1.0), 2)
            claim_rows.append((f"DSG-{claim_seq:07d}", s.policy_segment,
                               acc.date().isoformat(), ay, paid, round(inc - paid, 2), inc))
        bench.append((lob, ay, ep, round(seg_incurred, 2)))

premium = pd.DataFrame(prem_rows, columns=["policy_segment", "accident_year", "earned_premium"])
claims = pd.DataFrame(claim_rows, columns=["claim_id", "policy_segment", "accident_date",
                                           "accident_year", "paid", "outstanding", "incurred"])
print(f"{len(claims):,} claims · {len(premium):,} premium rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Write the source tables

# COMMAND ----------

spark.createDataFrame(claims).write.mode("overwrite").option("overwriteSchema", "true") \
    .saveAsTable(f"{fqn}.dsg_claims_src")
spark.createDataFrame(premium).write.mode("overwrite").option("overwriteSchema", "true") \
    .saveAsTable(f"{fqn}.dsg_premium_src")
spark.createDataFrame(segment).write.mode("overwrite").option("overwriteSchema", "true") \
    .saveAsTable(f"{fqn}.dsg_segment")

spark.sql(f"""COMMENT ON TABLE {fqn}.dsg_claims_src IS
'Use Case 4 canvas source: claim-grain, only policy_segment (no LOB/region/channel) '
'so the join to dsg_segment is a real canvas step. Amounts GBP. Synthetic data.'""")
spark.sql(f"""COMMENT ON TABLE {fqn}.dsg_premium_src IS
'Use Case 4 canvas source: earned premium by policy segment and accident year, GBP. '
'The premium branch of the monthly blend. Synthetic data.'""")
spark.sql(f"""COMMENT ON TABLE {fqn}.dsg_segment IS
'Use Case 4 lookup: policy_segment → line of business / region / channel (the VLOOKUP). '
'Synthetic data.'""")
print("✓ dsg_claims_src, dsg_premium_src, dsg_segment")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The benchmark — what the coded pipeline would produce
# MAGIC
# MAGIC `02_parity` proves the Designer canvas output equals this, line of
# MAGIC business × accident year.

# COMMAND ----------

bench_df = pd.DataFrame(bench, columns=["line_of_business", "accident_year",
                                        "earned_premium", "incurred"])
bench_g = bench_df.groupby(["line_of_business", "accident_year"], as_index=False).sum()
bench_g["loss_ratio"] = (bench_g.incurred / bench_g.earned_premium).round(4)
bench_g["earned_premium"] = bench_g.earned_premium.round(2)
bench_g["incurred"] = bench_g.incurred.round(2)
spark.createDataFrame(bench_g).write.mode("overwrite").option("overwriteSchema", "true") \
    .saveAsTable(f"{fqn}.dsg_benchmark")
spark.sql(f"""COMMENT ON TABLE {fqn}.dsg_benchmark IS
'Use Case 4 benchmark: the loss-ratio summary the coded pipeline produces from the '
'same sources (LOB × accident year). The Designer canvas output must match this — '
'see 02_parity. Synthetic data.'""")
print(f"✓ dsg_benchmark — {bench_g.shape[0]} rows")
display(spark.table(f"{fqn}.dsg_benchmark").where("line_of_business='Motor'").orderBy("accident_year"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## The Excel extract (drag-onto-canvas beat)

# COMMAND ----------

import shutil

extract = (claims.merge(segment, on="policy_segment")
           .query("line_of_business == 'Motor' and accident_year == 2024"))
local = "/tmp/claims_extract.csv"
extract.to_csv(local, index=False)
shutil.copyfile(local, f"{vol_path}/claims_extract.csv")
print(f"✓ {len(extract):,} rows → {vol_path}/claims_extract.csv")

# COMMAND ----------

print("Sources ready. Build the canvas (README.md), then run 02_parity.")
