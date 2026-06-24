"""
process_organic.py
------------------
Processes a Meta Business Suite Instagram content export into
data/organic_posts.json for the dashboard.

Meta exports multiple files per export — this script automatically
identifies the correct IG posts file by checking for the expected
columns. Handles both CSV and XLSX formats.

Usage:
  python scripts/process_organic.py           # auto-detects file
  python scripts/process_organic.py --input path/to/file.xlsx

Meta export: Business Suite → Content → set date range → Export
Place the exported file(s) in the repo root before running.
"""

import json
import argparse
import glob
import pandas as pd
from pathlib import Path

# ── B&S owned accounts to exclude ──
BS_ACCOUNTS = {'barkerandstonehouse'}

# ── Username → clean creator name ──
CREATOR_MAP = {
    'my.lymingtonhome':       'Shannon (Lymington Home)',
    'behindnumberdeux':       'Nisha (Behind Numéro Deux)',
    'toby_rex_thegingerduo':  'The Gingers & Jenn',
    'life_at_the_lodge':      'Life At The Lodge',
    'stripesinthecity':       'Anna (Stripes in the City)',
    'houseofhetheringtons':   'Georgia Hetherington',
    'herlondonresidence':     'Her London Residence',
    'amelialucyhome':         'Amelia (Amelia Lucy Home)',
    'queensburycoffee':       'The Queensbury Coffee House',
    'miss_fash':              'Bolutife (Miss Fash)',
    'the_jolly_reno':         'The Jolly Reno',
    'sarahinsurrey':          'Sarah Parker',
    'east_shore_home':        'Ashley (East Shore Home)',
    'homebydaniellex':        'Danielle (Home by Danielle)',
    'monkeymews_':            'Imogen (MonkeyMews)',
    'no14hectorshouse':       "Jade (Hector's House)",
    'jarroldnorwich':         'Jarrolds Norwich',
    'leopard_print_stairs':   'Laura (Leopard Print Stairs)',
    'bethanyhome_':           'Bethany Tyson',
    'ourberkelyhome':         'Abbey (Our Berkeley Home)',
    'nerkesharogers':         'Nerkesha Rogers',
    'trees4trees':            'Trees4Trees',
}

# ── Creators who have been in paid campaigns ──
PAID_CREATORS = {
    'houseofhetheringtons', 'bethanyhome_', 'my.lymingtonhome',
    'amelialucyhome', 'miss_fash', 'no14hectorshouse',
    'monkeymews_', 'behindnumberdeux',
}

TYPE_MAP = {
    'IG reel':     'Reel',
    'IG carousel': 'Carousel',
    'IG image':    'Static',
    'IG story':    'Story',
}

# Columns that identify this as the IG posts file (not stories/FB)
IG_POSTS_COLS = {'Account username', 'Post type', 'Publish time', 'Likes', 'Saves'}


def read_file(path):
    """Read CSV or XLSX into a DataFrame."""
    suffix = Path(path).suffix.lower()
    if suffix == '.csv':
        return pd.read_csv(path)
    elif suffix in ('.xlsx', '.xls'):
        return pd.read_excel(path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")


def is_ig_posts_file(df):
    """Check this is the IG posts export (not stories or FB)."""
    return IG_POSTS_COLS.issubset(df.columns)


def find_ig_posts_file():
    """
    Search repo root for Meta export files and return the IG posts one.
    Meta exports multiple files — we identify the right one by columns.
    """
    candidates = glob.glob('*.csv') + glob.glob('*.xlsx') + glob.glob('*.xls')
    # Prioritise files with date-range style names (Meta export pattern)
    candidates.sort(key=lambda f: Path(f).stat().st_mtime, reverse=True)

    for path in candidates:
        try:
            df = read_file(path)
            if is_ig_posts_file(df):
                return path, df
        except Exception:
            continue
    return None, None


def main(input_path=None):
    if input_path:
        print(f"Reading {input_path}...")
        df = read_file(input_path)
        if not is_ig_posts_file(df):
            print("✗ This doesn't look like the IG posts export file.")
            print(f"  Expected columns including: {IG_POSTS_COLS}")
            return
    else:
        print("Searching for Meta IG posts export file...")
        input_path, df = find_ig_posts_file()
        if df is None:
            print("✗ Could not find a matching Meta export file in the repo root.")
            print("  Place the exported file(s) here and try again.")
            return
        print(f"Found: {input_path}")

    # Filter out B&S owned posts — keep only influencer posts
    influencer_df = df[~df['Account username'].isin(BS_ACCOUNTS)].copy()
    print(f"  Total rows: {len(df)} | B&S owned: {len(df) - len(influencer_df)} | Influencer: {len(influencer_df)}")

    if influencer_df.empty:
        print("✗ No influencer posts found after filtering.")
        return

    # Parse dates
    influencer_df['Publish time'] = pd.to_datetime(
        influencer_df['Publish time'], format='%m/%d/%Y %H:%M', errors='coerce'
    )
    influencer_df['date'] = influencer_df['Publish time'].dt.strftime('%Y-%m-%d')

    # Preserve existing product tags (manual edits in dashboard)
    existing_products = {}
    existing_path = Path('data/organic_posts.json')
    if existing_path.exists():
        try:
            with open(existing_path, encoding='utf-8') as f:
                existing = json.load(f)
            existing_products = {
                p['permalink']: p.get('product', '')
                for p in existing if p.get('permalink')
            }
            tagged = sum(1 for v in existing_products.values() if v)
            print(f"  Preserving {tagged} existing product tags")
        except Exception as e:
            print(f"  Warning: could not read existing organic_posts.json ({e})")

    posts = []
    for idx, (_, row) in enumerate(influencer_df.iterrows()):
        uname    = str(row.get('Account username', '')).strip()
        is_paid  = uname in PAID_CREATORS
        creator  = CREATOR_MAP.get(uname, str(row.get('Account name', uname)))
        handle   = f"@{uname}" if uname else ''
        reach    = int(row['Reach'])    if pd.notna(row.get('Reach'))    and row.get('Reach', 0) != 0    else 0
        views    = int(row['Views'])    if pd.notna(row.get('Views'))    else 0
        likes    = int(row['Likes'])    if pd.notna(row.get('Likes'))    else 0
        comments = int(row['Comments']) if pd.notna(row.get('Comments')) else 0
        saves    = int(row['Saves'])    if pd.notna(row.get('Saves'))    else 0
        permalink= str(row.get('Permalink', '')) if pd.notna(row.get('Permalink')) else ''
        desc     = str(row.get('Description', ''))[:200] if pd.notna(row.get('Description')) else ''

        total_eng = likes + comments + saves
        if reach > 50000 or is_paid:
            tier = 'Macro'
        elif reach > 10000 or total_eng > 300:
            tier = 'Mid'
        else:
            tier = 'Micro'

        posts.append({
            "id":           idx + 1,
            "creator":      creator,
            "platform":     "Instagram",
            "handle":       handle,
            "tier":         tier,
            "date":         row['date'],
            "content_type": TYPE_MAP.get(str(row.get('Post type', '')), str(row.get('Post type', ''))),
            "product":      existing_products.get(permalink, ''),
            "reach":        reach,
            "impressions":  views,
            "likes":        likes,
            "comments":     comments,
            "saves":        saves,
            "description":  desc,
            "permalink":    permalink,
            "gifted":       not is_paid,
            "paid":         is_paid,
        })

    out = Path('data/organic_posts.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(posts, f, indent=2, ensure_ascii=False)

    print(f"✓ Written {len(posts)} influencer posts to {out}")
    creators = set(p['creator'] for p in posts)
    print(f"  Creators ({len(creators)}): {', '.join(sorted(creators))}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default=None, help='Path to Meta IG posts export (CSV or XLSX)')
    args = parser.parse_args()
    main(args.input)
