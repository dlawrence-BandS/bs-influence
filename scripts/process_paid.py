"""
process_paid.py
---------------
Converts an Influencer-Report.xlsx export from Meta Ads Manager
into data/paid_ads.json for the dashboard.

Usage:
  pip install pandas openpyxl
  python scripts/process_paid.py --input path/to/Influencer-Report.xlsx

Defaults to looking for Influencer-Report.xlsx in the repo root.
"""

import json
import re
import argparse
import pandas as pd
from pathlib import Path

# Raw keys can appear in many forms in Ads Manager (underscores, spaces,
# "PA" suffix, trailing variant numbers, different casing). We normalise
# both these keys and the cleaned ad name before matching, so
# 'Miss Fash PA', 'miss_fash', 'Miss Fash 2' etc. all collapse to one row.
CREATOR_MAP = {
    'etherington':          'Georgia Hetherington',
    'bethany':              'Bethany Tyson',
    'Shannon':              'Shannon (Lymington Home)',
    'Amelialucyhome':       'Amelia (Amelia Lucy Home)',
    'Miss Fash':            'Bolutife (Miss Fash)',
    'Kates Georgian Home':  "Kate's Georgian Home",
    'behindnumberdeux':     'Nisha (Behind Numéro Deux)',
    'hectorshouse':         "Jade (Hector's House)",
    'imogen':               'Imogen (MonkeyMews)',
    'sarah':                'Sarah Parker',
    'lifeatlodge':          'Life At The Lodge',
    'thehoppyhome':         'The Hoppy Home',
    'sarahinsurre':         'Sarah Parker',          # ad is named '@sarahinsurre'
    'ralphs_home':          'Aisling & Ralph (Victorian Home)',
    # Influx Autumn campaign creators, in case their ads are named by handle
    'meaux.house':          'Holly (Meaux House)',
    'lifeinthewolds':       'Emily (Life in the Wolds)',
    'overdale_home':        'Claire (Overdale Home)',
    'sophiejaynehomes':     'Sophie (Sophie Jayne Homes)',
    'reynoldsresidence':    'Kayla (Reynolds Residence)',
    'thestylepad_uk':       'Louise (The Style Pad)',
    'east_shore_home':      'Ashley (East Shore Home)',
    'ourberkelyhome':       'Abbey (Our Berkeley Home)',
    'our.home.in.dorset':   'Sarah (Our Home in Dorset)',
    'thestylepad':          'Louise (The Style Pad)',   # Influx ads say 'The Style Pad'
}

def _normalize(name: str) -> str:
    """Lowercase, drop separators, strip 'PA'/'Copy' tags and trailing
    variant numbers so equivalent creator names collapse to one key."""
    tokens = re.split(r'[ _]+', name.strip())
    tokens = [t for t in tokens if t.lower() not in ('pa', 'copy') and not t.isdigit()]
    return re.sub(r'[^a-z0-9]', '', ''.join(tokens).lower())

NORMALIZED_MAP = {_normalize(k): v for k, v in CREATOR_MAP.items()}

# Influx ads are named like  c3_Partnership_Influx_<Creator Name>_<variant>
INFLUX_RE = re.compile(r'influx[_\s-]+([^_]+)', re.IGNORECASE)

def extract_creator(ad_name: str) -> str:
    m = INFLUX_RE.search(ad_name)
    if m:
        seg = m.group(1).strip()
        key = _normalize(seg)
        return NORMALIZED_MAP.get(key, seg)
    name = ad_name.replace('c3_influencer_', '').replace(' – Copy', '').strip()
    key = _normalize(name)
    if key in NORMALIZED_MAP:
        return NORMALIZED_MAP[key]
    # No match — fall back to a readable version of the raw name so it's
    # obviously "unmapped" on the dashboard rather than silently wrong.
    return name.replace('_', ' ').strip()

INFLUX_FILE = 'Influx-Report.xlsx'   # optional: Ads Manager export of the Influx ads

def main(input_path: str):
    print(f"Reading {input_path}...")
    df = pd.read_excel(input_path)

    # Influx ads are named differently, so they come from their own export.
    # Rows that appear in both files are kept once (the Influx file wins).
    if Path(INFLUX_FILE).exists():
        print(f"Reading {INFLUX_FILE}...")
        inf = pd.read_excel(INFLUX_FILE)
        df = pd.concat([df, inf], ignore_index=True)
        before = len(df)
        df = df.drop_duplicates(subset=['Day', 'Campaign name', 'Ad name'], keep='last')
        if before != len(df):
            print(f"  (dropped {before - len(df)} rows that were in both files)")
    else:
        print(f"  (no {INFLUX_FILE} found — Influx ads not included)")

    df['creator_name']  = df['Ad name'].apply(extract_creator)
    df['Day']           = pd.to_datetime(df['Day']).dt.strftime('%Y-%m-%d')
    df['Purchases']                    = df['Purchases'].fillna(0)
    df['Purchases conversion value']   = df['Purchases conversion value'].fillna(0)

    records = df.rename(columns={
        'Day':                          'date',
        'Campaign name':                'campaign',
        'Ad name':                      'ad_name',
        'Reach':                        'reach',
        'Clicks (all)':                 'clicks',
        'Purchases':                    'purchases',
        'Purchases conversion value':   'conversion_value',
        'Amount spent (GBP)':           'spend',
    })[[
        'date','creator_name','campaign','ad_name',
        'reach','clicks','purchases','conversion_value','spend'
    ]].to_dict(orient='records')

    out = Path('data/paid_ads.json')
    with open(out, 'w') as f:
        json.dump(records, f, indent=2, default=str)

    print(f"✓ Written {len(records)} rows to {out}")
    total_spend = sum(r['spend'] for r in records)
    total_rev   = sum(r['conversion_value'] for r in records)
    print(f"  Spend: £{total_spend:,.2f}  |  Conv. value: £{total_rev:,.2f}  |  ROAS: {total_rev/total_spend:.1f}x")
    inf_rows = [r for r in records if 'influx' in str(r['ad_name']).lower()]
    if inf_rows:
        s = sum(r['spend'] for r in inf_rows)
        print(f"  of which Influx: {len(inf_rows)} rows, £{s:,.2f} spend")

    # ── Per-creator totals (used for the Daily Breakdown table default view) ──
    grouped = df.groupby('creator_name').agg(
        reach=('Reach', 'sum'),
        clicks=('Clicks (all)', 'sum'),
        purchases=('Purchases', 'sum'),
        conversion_value=('Purchases conversion value', 'sum'),
        spend=('Amount spent (GBP)', 'sum'),
        first_date=('Day', 'min'),
        last_date=('Day', 'max'),
    ).reset_index()
    grouped['roas'] = grouped.apply(
        lambda r: round(r['conversion_value'] / r['spend'], 2) if r['spend'] else 0, axis=1
    )
    grouped = grouped.rename(columns={'creator_name': 'creator'})
    grouped = grouped.sort_values('spend', ascending=False)

    creator_totals = grouped.to_dict(orient='records')
    totals_out = Path('data/paid_ads_by_creator.json')
    with open(totals_out, 'w') as f:
        json.dump(creator_totals, f, indent=2, default=str)
    print(f"✓ Written {len(creator_totals)} creator totals to {totals_out}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='Influencer-Report.xlsx')
    args = parser.parse_args()
    main(args.input)
