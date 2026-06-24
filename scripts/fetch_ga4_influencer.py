"""
fetch_ga4_influencer.py
-----------------------
Queries GA4 BigQuery for sessions and revenue driven by utm_medium=influencer.
Writes output to data/ga4_influencer.json for the GitHub Pages dashboard.

Usage:
  pip install google-cloud-bigquery
  python scripts/fetch_ga4_influencer.py

Requires: GOOGLE_APPLICATION_CREDENTIALS env var pointing to your service account JSON.
Schedule via GitHub Actions (see .github/workflows/refresh_data.yml) or run locally.
"""

import json
from datetime import datetime, timedelta
from google.cloud import bigquery

PROJECT_ID = "commanding-air-450109-p0"
DATASET_ID = "analytics_287404213"
OUTPUT_PATH = "data/ga4_influencer.json"

# How many days back to pull
LOOKBACK_DAYS = 180

client = bigquery.Client(project=PROJECT_ID)

query = f"""
WITH events AS (
  SELECT
    PARSE_DATE('%Y%m%d', event_date) AS date,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'source') AS utm_source,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'medium') AS utm_medium,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'campaign') AS utm_campaign,
    event_name,
    (SELECT value.double_value FROM UNNEST(event_params) WHERE key = 'value') AS revenue,
    user_pseudo_id,
    stream_id
  FROM `{PROJECT_ID}.{DATASET_ID}.events_*`
  WHERE _TABLE_SUFFIX >= FORMAT_DATE('%Y%m%d', DATE_SUB(CURRENT_DATE(), INTERVAL {LOOKBACK_DAYS} DAY))
    AND (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'medium') = 'influencer'
),

sessions AS (
  SELECT
    date,
    utm_source AS creator,
    utm_campaign AS campaign,
    COUNT(DISTINCT CONCAT(user_pseudo_id, CAST(stream_id AS STRING))) AS sessions
  FROM events
  WHERE event_name = 'session_start'
  GROUP BY 1, 2, 3
),

purchases AS (
  SELECT
    date,
    utm_source AS creator,
    utm_campaign AS campaign,
    COUNT(*) AS transactions,
    SUM(revenue) AS revenue
  FROM events
  WHERE event_name = 'purchase'
  GROUP BY 1, 2, 3
)

SELECT
  s.date,
  s.creator,
  s.campaign,
  s.sessions,
  COALESCE(p.transactions, 0) AS transactions,
  COALESCE(p.revenue, 0) AS revenue
FROM sessions s
LEFT JOIN purchases p
  ON s.date = p.date AND s.creator = p.creator AND s.campaign = p.campaign
ORDER BY s.date DESC
"""

print("Running GA4 influencer query...")
df = client.query(query).to_dataframe()

# Serialise dates for JSON
df["date"] = df["date"].astype(str)

records = df.to_dict(orient="records")
output = {
    "updated_at": datetime.utcnow().isoformat() + "Z",
    "lookback_days": LOOKBACK_DAYS,
    "rows": records
}

with open(OUTPUT_PATH, "w") as f:
    json.dump(output, f, indent=2)

print(f"Wrote {len(records)} rows to {OUTPUT_PATH}")
