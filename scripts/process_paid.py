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
import argparse
import pandas as pd
from pathlib import Path

CREATOR_MAP = {
    'etherington':          'Georgia Hetherington',
    'bethany':              'Bethany Tyson',
    'bethany PA':           'Bethany Tyson',
    'Shannon':              'Shannon (Lymington Home)',
    'Shannon PA':           'Shannon (Lymington Home)',
    'Amelialucyhome':       'Amelia (Amelia Lucy Home)',
    'Amelialucyhome PA':    'Amelia (Amelia Lucy Home)',
    'Miss Fash PA':         'Bolutife (Miss Fash)',
    'Kates Georgian Home PA': "Kate's Georgian Home",
    'behindnumberdeux':     'Nisha (Behind Numéro Deux)',
    'hectorshouse PA':      "Jade (Hector's House)",
    'hectorshouse':         "Jade (Hector's House)",
    'imogen PA':            'Imogen (MonkeyMews)',
    'imogen':               'Imogen (MonkeyMews)',
}

def extract_creator(ad_name: str) -> str:
    name = ad_name.replace('c3_influencer_', '').replace(' – Copy', '').replace('_PA', '').strip()
    return name.replace('_', ' ').strip()

def main(input_path: str):
    print(f"Reading {input_path}...")
    df = pd.read_excel(input_path)

    df['creator_clean'] = df['Ad name'].apply(extract_creator)
    df['creator_name']  = df['creator_clean'].map(CREATOR_MAP).fillna(df['creator_clean'])
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

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='Influencer-Report.xlsx')
    args = parser.parse_args()
    main(args.input)
