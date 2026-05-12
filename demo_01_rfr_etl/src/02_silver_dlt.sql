-- Databricks notebook source
-- MAGIC %md
-- MAGIC # Silver — `silver_rfr_curves` (DLT)
-- MAGIC
-- MAGIC Reads the wide bronze table, unpivots EUR/GBP/USD into rows, types and
-- MAGIC validates each row, and derives a 1-year forward rate per
-- MAGIC (effective_date, currency).
-- MAGIC
-- MAGIC The four `CONSTRAINT ... EXPECT ... ON VIOLATION DROP ROW` clauses are
-- MAGIC the formal version of the VBA `IsNumeric` checks the actuary's macros
-- MAGIC did silently. Rows that fail are dropped; the DLT event log records the
-- MAGIC violation counts so the actuary can see them in the pipeline UI.

-- COMMAND ----------

CREATE OR REFRESH MATERIALIZED VIEW silver_rfr_curves(
  CONSTRAINT valid_effective_date  EXPECT (effective_date IS NOT NULL)
    ON VIOLATION DROP ROW,
  CONSTRAINT valid_currency        EXPECT (currency IN ('EUR','GBP','USD'))
    ON VIOLATION DROP ROW,
  CONSTRAINT valid_maturity_range  EXPECT (maturity_months BETWEEN 12 AND 360)
    ON VIOLATION DROP ROW,
  CONSTRAINT valid_rate_range      EXPECT (spot_rate BETWEEN -0.05 AND 0.20)
    ON VIOLATION DROP ROW
)
COMMENT 'Long-form EIOPA risk-free spot curves, one row per (effective_date, currency, maturity), with a derived 1-year forward rate per curve.'
TBLPROPERTIES (
  'pipelines.expectations.layered' = 'bronze',
  'delta.feature.allowColumnDefaults' = 'supported'
)
AS
WITH unpivoted AS (
  SELECT
    effective_date,
    -- Stack the three currency columns into (currency, spot_rate) rows.
    stack(3,
      'EUR', EUR,
      'GBP', GBP,
      'USD', USD
    ) AS (currency, spot_rate),
    maturity_years * 12 AS maturity_months,
    _ingested_at,
    _source_file
  FROM live.bronze_rfr_curves
)
SELECT
  effective_date,
  currency,
  maturity_months,
  CAST(spot_rate AS DOUBLE) AS spot_rate,
  -- 1-year forward rate at maturity m, starting at maturity m-12 months.
  -- f = (1+s_m)^t_m / (1+s_{m-12})^t_{m-12} - 1, with t in years.
  -- Returns NULL at the 12-month maturity (no preceding point).
  CASE
    WHEN LAG(spot_rate) OVER (PARTITION BY effective_date, currency ORDER BY maturity_months) IS NULL
      THEN CAST(NULL AS DOUBLE)
    ELSE
      POWER(1.0 + spot_rate, maturity_months / 12.0)
      / POWER(1.0 + LAG(spot_rate) OVER (PARTITION BY effective_date, currency ORDER BY maturity_months),
              (maturity_months - 12) / 12.0)
      - 1.0
  END AS forward_rate_1y,
  _ingested_at,
  _source_file
FROM unpivoted
WHERE spot_rate IS NOT NULL
