"""
pipeline.py — Main orchestrator for the Ironsite construction video analysis pipeline.
Handles --mode flag (augmented, baseline, rules_only), owns GeminiBudgetTracker.
"""
import os
import sys
import json
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import List

from . import config
from . import video_io
from . import scene_select
from . import sidecar as sidecar_module
from . import events as events_module
from . import metrics as metrics_module
from . import render_report
from .spatial_query import GeminiBudgetTracker

log = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Ironsite Construction Video Analysis Pipeline"
    )
    parser.add_argument("--input_dir", required=True,
                        help="Directory containing input MP4 videos")
    parser.add_argument("--out_dir", required=True,
                        help="Base output directory")
    parser.add_argument("--mode", choices=["augmented", "baseline", "rules_only"],
                        default=None,
                        help="Run mode: augmented (default), baseline, or rules_only")

    # Legacy flags
    parser.add_argument("--baseline", action="store_true",
                        help="Legacy: equivalent to --mode baseline")
    parser.add_argument("--no_llm", action="store_true",
                        help="Legacy: equivalent to --mode rules_only")
    parser.add_argument("--use_llm", action="store_true",
                        help="Legacy: equivalent to --mode augmented")

    # Optional config overrides
    parser.add_argument("--max_videos", type=int, default=None,
                        help="Max number of videos to process")
    parser.add_argument("--max_minutes_per_video", type=float, default=None,
                        help="Max minutes per video to analyze")
    parser.add_argument("--sample_every_sec", type=float, default=None,
                        help="Uniform sampling interval in seconds")
    parser.add_argument("--spatial_query_k", type=int, default=None,
                        help="Top-K events for spatial query")
    parser.add_argument("--gemini_budget", type=int, default=None,
                        help="Gemini call budget for augmented mode")
    parser.add_argument("--gemini_budget_baseline", type=int, default=None,
                        help="Gemini call budget for baseline mode")

    args = parser.parse_args()

    # Resolve mode from legacy flags
    if args.mode is None:
        if args.baseline:
            args.mode = "baseline"
        elif args.no_llm:
            args.mode = "rules_only"
        elif args.use_llm:
            args.mode = "augmented"
        else:
            args.mode = "augmented"

    return args


def run_pipeline(args):
    """Main pipeline execution."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    log.info(f"=" * 60)
    log.info(f"IRONSITE CONSTRUCTION VIDEO ANALYSIS PIPELINE")
    log.info(f"Mode: {args.mode}")
    log.info(f"Input: {args.input_dir}")
    log.info(f"=" * 60)

    # Validate API key for modes that need it
    if args.mode in ("augmented", "baseline"):
        if not os.environ.get("GEMINI_API_KEY"):
            log.error("GEMINI_API_KEY environment variable not set!")
            log.error("Run: export GEMINI_API_KEY='your-key-here'")
            sys.exit(1)

    # Apply config overrides
    if args.sample_every_sec:
        config.SAMPLE_EVERY_SEC = args.sample_every_sec
    if args.spatial_query_k:
        config.SPATIAL_QUERY_K = args.spatial_query_k
    if args.gemini_budget:
        config.GEMINI_BUDGET = args.gemini_budget
    if args.gemini_budget_baseline:
        config.GEMINI_BUDGET_BASELINE = args.gemini_budget_baseline

    # Create output directory
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(args.out_dir, f"{run_id}")
    os.makedirs(output_dir, exist_ok=True)
    log.info(f"Output directory: {output_dir}")

    # Discover videos
    video_files = video_io.list_videos(args.input_dir)
    if args.max_videos:
        video_files = video_files[:args.max_videos]

    if not video_files:
        log.error(f"No MP4 files found in {args.input_dir}")
        sys.exit(1)

    # Get video info
    video_infos = []
    video_paths = {}  # filename -> full path
    for vf in video_files:
        info = video_io.get_video_info(vf)
        if info:
            video_infos.append(info)
            video_paths[info["filename"]] = vf
        else:
            log.warning(f"Skipping unreadable video: {vf}")

    log.info(f"Processing {len(video_infos)} videos")

    # Route to appropriate mode
    if args.mode == "baseline":
        _run_baseline(video_infos, video_paths, output_dir, args)
    elif args.mode == "rules_only":
        _run_augmented_or_rules(video_infos, video_paths, output_dir, args, use_llm=False)
    else:  # augmented
        _run_augmented_or_rules(video_infos, video_paths, output_dir, args, use_llm=True)

    log.info(f"=" * 60)
    log.info(f"PIPELINE COMPLETE")
    log.info(f"Output: {output_dir}")
    log.info(f"=" * 60)


def _run_augmented_or_rules(
    video_infos: List[dict],
    video_paths: dict,
    output_dir: str,
    args,
    use_llm: bool,
):
    """Run augmented or rules_only pipeline."""
    all_keyframes = []
    all_candidates = []

    # --- Phase 1: Scene Selection ---
    log.info("=" * 40)
    log.info("PHASE 1: Scene Selection")
    log.info("=" * 40)

    for vinfo in video_infos:
        vpath = video_paths[vinfo["filename"]]
        log.info(f"Selecting frames from {vinfo['filename']} "
                 f"({vinfo['duration_sec']:.0f}s)")

        keyframes, candidates = scene_select.select_frames(
            vpath, vinfo,
            sample_every_sec=args.sample_every_sec or config.SAMPLE_EVERY_SEC,
            max_minutes=args.max_minutes_per_video,
        )

        all_keyframes.extend(keyframes)
        all_candidates.extend(candidates)

    log.info(f"Total keyframes selected: {len(all_keyframes)}")
    log.info(f"Total event candidates: {len(all_candidates)}")

    # --- Phase 2: Sidecar Construction ---
    log.info("=" * 40)
    log.info("PHASE 2: Sidecar Construction (Depth + Detection)")
    log.info("=" * 40)

    enriched_keyframes = []
    for vinfo in video_infos:
        vpath = video_paths[vinfo["filename"]]
        vid_kfs = [kf for kf in all_keyframes if kf["video_file"] == vinfo["filename"]]

        if not vid_kfs:
            continue

        log.info(f"Building sidecar for {vinfo['filename']} ({len(vid_kfs)} keyframes)")

        enriched = sidecar_module.build_sidecar_for_video(
            vpath, vinfo, vid_kfs, output_dir,
        )
        enriched_keyframes.extend(enriched)

    log.info(f"Total enriched keyframes: {len(enriched_keyframes)}")

    # --- Phase 3: Event Extraction ---
    log.info("=" * 40)
    log.info("PHASE 3: Event Extraction")
    log.info("=" * 40)

    events = events_module.extract_events(
        enriched_keyframes, video_paths, output_dir,
    )
    log.info(f"Total events extracted: {len(events)}")

    # --- Phase 4: Spatial Query (augmented only) ---
    tracker = None
    if use_llm:
        log.info("=" * 40)
        log.info("PHASE 4: Spatial Query Loop")
        log.info("=" * 40)

        budget = args.gemini_budget or config.GEMINI_BUDGET
        tracker = GeminiBudgetTracker(budget)

        from . import spatial_query
        events = spatial_query.run_spatial_queries(
            events, enriched_keyframes, video_paths, output_dir,
            tracker,
            top_k=args.spatial_query_k or config.SPATIAL_QUERY_K,
        )
        log.info(f"Gemini budget after spatial queries: {tracker}")

    # --- Phase 5: Metrics ---
    log.info("=" * 40)
    log.info("PHASE 5: Metrics Computation")
    log.info("=" * 40)

    metrics = metrics_module.compute_all_metrics(events, enriched_keyframes)
    log.info(f"Safety: {metrics['safety']['score']}/100")
    log.info(f"Ergonomics: {metrics['ergonomics']['score']}/100")
    log.info(f"Productivity: {metrics['productivity']['score']}/100")
    log.info(f"Quality: {metrics['quality']['score']}/100")

    # --- Phase 6: Report Generation ---
    log.info("=" * 40)
    log.info("PHASE 6: Report Generation")
    log.info("=" * 40)

    narratives = None
    if use_llm and tracker:
        from . import report_llm
        narratives = {}

        log.info("Generating Gemini narratives...")
        narratives["headlines"] = report_llm.generate_headlines(
            events, metrics, tracker
        )
        for section in ["safety", "ergonomics", "productivity", "quality"]:
            narratives[section] = report_llm.generate_narrative_section(
                section, events, metrics, enriched_keyframes, tracker
            )
        log.info(f"Gemini budget after narratives: {tracker}")

    report_path = render_report.render_augmented_report(
        events, metrics, enriched_keyframes, video_infos,
        output_dir, narratives,
    )

    # Save sidecar JSON
    sidecar_data = {
        "run_mode": "augmented" if use_llm else "rules_only",
        "run_timestamp": datetime.now().isoformat(),
        "videos": [{"filename": v["filename"], "duration_sec": v["duration_sec"]}
                   for v in video_infos],
        "keyframe_count": len(enriched_keyframes),
        "event_count": len(events),
        "metrics": metrics,
        "events": events,
        "keyframes": enriched_keyframes,
        "gemini_budget": {
            "total": tracker.budget if tracker else 0,
            "used": tracker.used if tracker else 0,
        },
    }
    sidecar_path = sidecar_module.save_sidecar(sidecar_data, output_dir)

    log.info(f"Report: {report_path}")
    log.info(f"Sidecar: {sidecar_path}")


def _run_baseline(
    video_infos: List[dict],
    video_paths: dict,
    output_dir: str,
    args,
):
    """Run baseline naive pipeline."""
    from . import report_llm

    budget = args.gemini_budget_baseline or config.GEMINI_BUDGET_BASELINE
    tracker = GeminiBudgetTracker(budget)

    # Determine frames per video (spread evenly by duration)
    total_duration = sum(v["duration_sec"] for v in video_infos)
    max_frames = config.BASELINE_MAX_FRAMES

    all_sample_frames = []
    frames_dir = os.path.join(output_dir, "frames")
    clips_dir = os.path.join(output_dir, "clips")
    os.makedirs(frames_dir, exist_ok=True)
    os.makedirs(clips_dir, exist_ok=True)

    log.info("=" * 40)
    log.info("BASELINE: Uniform Frame Sampling")
    log.info("=" * 40)

    for vinfo in video_infos:
        # Allocate frames proportional to duration
        vid_frames = max(1, int(max_frames * vinfo["duration_sec"] / max(total_duration, 1)))
        timestamps = scene_select.uniform_sample_timestamps(vinfo, vid_frames)

        vpath = video_paths[vinfo["filename"]]

        for ts in timestamps:
            frame = video_io.extract_frame_at_time(vpath, ts)
            if frame is None:
                continue

            frame_id = f"baseline_{vinfo['filename']}_{ts:.1f}s"
            frame_path = os.path.join(frames_dir, f"{frame_id}.jpg")
            video_io.save_frame(frame, frame_path, config.FRAME_SAVE_SIZE)

            sample_frame = {
                "frame_id": frame_id,
                "video_file": vinfo["filename"],
                "timestamp_sec": ts,
                "timestamp_fmt": video_io.format_timestamp(ts),
                "frame_path": os.path.relpath(frame_path, output_dir),
                "full_frame_path": frame_path,
            }
            all_sample_frames.append(sample_frame)

        # Cut clips at uniform intervals for clip reel
        clip_timestamps = timestamps[:3]  # Just first few for clip reel
        for i, ts in enumerate(clip_timestamps):
            clip_name = f"baseline_clip_{len(all_sample_frames) - len(timestamps) + i}.mp4"
            clip_path = os.path.join(clips_dir, clip_name)
            video_io.cut_clip(vpath, ts, clip_path)

    log.info(f"Sampled {len(all_sample_frames)} baseline frames")

    # Process in chunks
    log.info("=" * 40)
    log.info("BASELINE: Gemini Chunk Summaries")
    log.info("=" * 40)

    chunk_size = config.BASELINE_CHUNK_SIZE
    summaries = []

    for i in range(0, len(all_sample_frames), chunk_size):
        chunk = all_sample_frames[i:i + chunk_size]
        log.info(f"Processing baseline chunk {i // chunk_size + 1} "
                 f"({len(chunk)} frames)")

        summary = report_llm.generate_baseline_summary(chunk, i // chunk_size, tracker)
        if summary:
            summaries.append(summary)

    # Merge summaries
    log.info("Merging baseline summaries...")
    merged = report_llm.merge_baseline_summaries(summaries, tracker)

    # Render baseline report
    report_path = render_report.render_baseline_report(
        merged, all_sample_frames, video_infos, output_dir,
    )

    # Save minimal sidecar
    sidecar_data = {
        "run_mode": "baseline",
        "run_timestamp": datetime.now().isoformat(),
        "videos": [{"filename": v["filename"], "duration_sec": v["duration_sec"]}
                   for v in video_infos],
        "frame_count": len(all_sample_frames),
        "gemini_budget": {"total": tracker.budget, "used": tracker.used},
    }
    sidecar_path = sidecar_module.save_sidecar(sidecar_data, output_dir)

    log.info(f"Baseline report: {report_path}")
    log.info(f"Sidecar: {sidecar_path}")
    log.info(f"Gemini budget: {tracker}")


def main():
    args = parse_args()
    run_pipeline(args)


if __name__ == "__main__":
    main()
