# CS2 Demo Analyse

Batch pipeline for CS2 team demo analysis:

1. Read `RosterVisualisation/Data` from Google Sheets, including `SteamID`.
2. Read the current demo list directly from the public Google Drive `Replays/Data` folder. The demo list is never read from a Sheet.
3. Compare the Drive folder manifest with published/local output cache, then download and parse only new or changed demos.
4. Detect package format by content, extract the single demo, and parse player stats with `demoparser2`.
5. Generate modular static-site data for the HTML analyst dashboard.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
```

Google API credentials are optional. The update pipeline reads the public Drive
folder through Google's anonymous embedded-folder view, and falls back to
authenticated APIs only if public scraping fails.

When available, Application Default Credentials can be used for authenticated
Drive downloads:

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

Share the Drive folder and Sheets with that service account email when using
authenticated Google APIs.

## Commands

```bash
# Final deployment/update entry point:
# - clone/pull https://github.com/Rotch512/WOSTCS2 into .cache/github/WOSTCS2
# - restore the previously published output cache when complete
# - sync roster from Sheets and demos from the Drive folder
# - analyze only new/changed demos
# - publish web, output data, and source back to GitHub
./update_wostcs2.sh

# Repeatable production run:
# - sync roster from Sheets
# - read Replays/Data directly from the Drive folder
# - download only new/changed demo packages
# - parse demos
# - update modular output data
cs2demo run

# Individual steps:
cs2demo sync-roster

# List Replays/Data from Google Drive folder and update output/demo_manifest.json
cs2demo sync-drive-index

# Download demo packages listed by the manifest/replay cache
cs2demo download

# Extract SteamID + nicknames from all demos, without final team statistics
cs2demo discover

# Create a starter identity review CSV from discovered players
cs2demo init-identity

# Generate long-term team summary and per-match detail files
cs2demo summarize

# Remove a bad demo from generated data by Drive file_id or exact file name.
# Local demo caches are kept unless --delete-cache is explicitly passed.
cs2demo delete-demo <file_id-or-demo-name>
```

Open `web/index.html` and point it at the generated `output` directory data when serving both from the same static host.

## Data Layout

Generated site data is intentionally split so routine page loads do not fetch
all round-level data:

- `output/demo_manifest.json`: current Drive folder file ledger and processing states.
- `output/sheets/replays_filter.csv`: generated from Drive folder filenames, not from Sheets.
- `output/sheets/roster.csv`: roster source copied from Google Sheets.
- `output/summary.json`: compact dashboard index with player aggregates, map aggregates, player-match rows, compact team match rows, and per-match `detail_path` values.
- `output/match_details/<file_id>.json`: round-level data for one match, loaded only by `web/match.html`.
- `output/matches/<file_id>.json`: parser cache for one match, used by the update pipeline.
- `output/player_match_stats.json`: index for the per-match parser cache files.

## Deployment

`./update_wostcs2.sh` is the single automation entry point for maintaining the
public GitHub Pages site. It keeps the publish repository in
`.cache/github/WOSTCS2` by default, uses GitHub as the published data source of
truth, and keeps demo package/demo extraction caches under `.cache/cs2demo`.

Before pushing published site updates, make sure:

```bash
gh auth login
```

If GitHub CLI is not used, configure regular git HTTPS credentials or SSH access
for `https://github.com/Rotch512/WOSTCS2.git`.

Useful overrides:

```bash
WOST_PAGES_DIR=/path/to/WOSTCS2 ./update_wostcs2.sh
WOST_PUBLISH_BRANCH=gh-pages ./update_wostcs2.sh
CS2_CACHE_DIR=/path/to/demo-cache ./update_wostcs2.sh
```

The script deliberately does not delete local demo caches during normal runs.
Use `cs2demo delete-demo <selector> --delete-cache` for targeted cache removal,
or delete `.cache/cs2demo/packages` and `.cache/cs2demo/demos` when doing a full
from-zero rebuild.

Roster is the identity source. `RosterVisualisation/Data` must include `Player`,
`Start`, `End`, `Status`, and `SteamID`. `Starter`, `Stand-in`, and `Benched`
are counted; `Left` is not counted.

`Rating` is a transparent Rating 3.0 proxy based on HLTV-public sub-rating
categories: Kill, Damage, Survival, KAST, Multi-Kill, and a Round Swing proxy.
It is not HLTV's private formula.
