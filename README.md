# Ironsite — Construction Video Analysis Pipeline

> AI-powered "Daily Newspaper" report for construction supervisors — evidence-backed, timestamped, and auditable.

## Quick Start

```bash
# 1. Set API key
export GEMINI_API_KEY="your-key-here"

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run pipeline
python -m src.pipeline \
  --input_dir ./IronsiteHackathonData \
  --out_dir ./outputs \
  --mode augmented
```

## Run Modes

| Mode | Description | Gemini Calls |
|------|-------------|-------------|
| `augmented` | Full sidecar + spatial query + Gemini narrative | ≤200 |
| `baseline` | Naive uniform sampling + Gemini summary | ≤100 |
| `rules_only` | Full sidecar + rule-based report, zero Gemini | 0 |

## Architecture

```
Input MP4s → Scene Selection → Depth + Detection → Sidecar
  → Event Extraction → Metrics → [Spatial Query] → Report
```

## Output Structure

```
outputs/YYYYMMDD_HHMMSS/
├── sidecar.json          # Full evidence sidecar
├── report.md             # Augmented/rules-only report
├── report_baseline.md    # Baseline comparison (baseline mode)
├── clips/                # Event clips (MP4)
├── frames/               # Keyframe images (JPG)
└── crops/                # Spatial query crops (JPG)
```

## CLI Options

```
--max_videos N                Max videos to process
--max_minutes_per_video M     Cap minutes per video
--sample_every_sec S          Sampling interval (default: 2.0)
--spatial_query_k K           Top-K events for spatial query (default: 20)
--gemini_budget N             Augmented mode budget (default: 200)
--gemini_budget_baseline N    Baseline mode budget (default: 100)
```
