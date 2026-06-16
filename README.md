# CS2 Demo Analyse

Batch pipeline for CS2 team demo analysis:

1. Read `RosterVisualisation/Data` from Google Sheets, including `SteamID`.
2. Maintain `analysis_manifest.json` in Google Drive `Replays/Data` as the analyzed-demo ledger.
3. Compare the manifest with current files in `Replays/Data`, then download and parse only new or changed demos.
4. Detect package format by content, extract the single demo, and parse player stats with `demoparser2`.
5. Generate long-term `summary.json` for the HTML analyst dashboard.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
```

For Google APIs, use Application Default Credentials or a service account:

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

Share the Drive folder and Sheets with that service account email.

## Commands

```bash
# Final deployment/update entry point:
# - clone/pull https://github.com/Rotch512/WOSTCS2 into .cache/github/WOSTCS2
# - restore the previously published output cache
# - sync Google Sheets and Drive demos
# - analyze only new/changed demos
# - publish web, output data, and source back to GitHub
./update_wostcs2.sh

# Repeatable production run:
# - sync Google Sheets
# - read/update Replays/Data/analysis_manifest.json
# - download only new/changed demo packages
# - parse demos
# - update output/summary.json
cs2demo run

# Individual steps:
cs2demo sync-sheets

# List Replays/Data and update output/demo_manifest.json
cs2demo sync-drive-index

# Download demo packages listed by the manifest/replay cache
cs2demo download

# Extract SteamID + nicknames from all demos, without final team statistics
cs2demo discover

# Create a starter identity review CSV from discovered players
cs2demo init-identity

# Generate long-term team summary after player_identity.csv has been reviewed
cs2demo summarize
```

Open `web/index.html` and point it at the generated `output` directory data when serving both from the same static host.

## Deployment

`./update_wostcs2.sh` is the single automation entry point for maintaining the
public GitHub Pages site. It keeps the publish repository in
`.cache/github/WOSTCS2` by default, uses GitHub as the published data source of
truth, and keeps demo package/demo extraction caches under `.cache/cs2demo`.

Before running it, make sure:

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
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

The script deliberately does not delete local demo caches. After the pipeline is
stable, `.cache/cs2demo/packages` and `.cache/cs2demo/demos` can be removed
manually to reclaim disk space.

Roster is the identity source. `RosterVisualisation/Data` must include `Player`,
`Start`, `End`, `Status`, and `SteamID`. `Starter`, `Stand-in`, and `Benched`
are counted; `Left` is not counted.

`Rating` is a transparent Rating 3.0 proxy based on HLTV-public sub-rating
categories: Kill, Damage, Survival, KAST, Multi-Kill, and a Round Swing proxy.
It is not HLTV's private formula.
