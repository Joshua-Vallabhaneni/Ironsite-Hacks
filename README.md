# Jarvis
### Construction Intelligence using Spatial Evidence and Voice AI

## What is this?

Jarvis takes hours of raw construction headcam footage and turns it into a supervisor-facing daily report.

A construction worker wears a headcam all day. That footage gets uploaded to our web portal. Jarvis processes it, scores the workday across Safety, Ergonomics, Productivity and Quality, and delivers a structured timestamped report with short clips of everything worth reviewing. Then Jarvis, our voice AI agent, lets the supervisor ask questions about the day and get cited evidence-backed answers in real time.

## The Problem

Construction headcam footage contains dense safety and productivity signal that goes unreviewed at scale. Supervisors cannot manually audit hours of egocentric video per worker per shift, creating systematic blind spots in hazard detection, productivity analysis and quality verification.

Applying SOTA vision-language models directly to this footage does not solve the problem. The spatial intelligence gap in current VLMs is well-documented and measurable across benchmarks:

- State-of-the-art VLMs consistently fail at depth and height perception even when performing well on simpler geometric properties (GeoMeter Benchmark, CVPRW 2025)
- VLMs systematically misallocate attention on spatial queries, failing to focus on the relevant image regions particularly for relational concepts such as in front of or behind (AdaptVis, ICML 2025)
- Even simple left and right localization remains a known failure mode for existing visual-language models (LocVLM, CVPR 2024)
- Egocentric construction video requires evidence-dense moment retrieval rather than holistic summarization to support reliable quality supervision (EgoConQS, Automation in Construction 2025)

These are systematic failures that make single-pass VLM inference unreliable for this task.

## How It Works

**Login and Upload.** Supervisor uploads headcam footage via the web portal.

**Backend Pipeline.** Four stages process the footage and build a full spatial understanding of the workday.

**Analytics Dashboard.** Scored metrics across all four indices with timestamped evidence.

**Jarvis Voice Agent.** Interactive voice AI that ingests the report and answers questions about the day.

## What Makes This Novel

Most AI applied to construction footage does object detection. It recognizes a hardhat or a ladder. Jarvis does something fundamentally different across four stages.

**Depth-aware spatial intelligence.** Standard models see footage as flat 2D images. Jarvis runs MiDaS depth estimation, MediaPipe hand tracking and YOLOv8 tool detection in parallel on every keyframe, fusing them into a spatial evidence file that captures real 3D distances, interaction density and hand-tool overlap. We measure the workspace rather than just describe it. This directly solves the depth and height perception failure documented by the GeoMeter Benchmark.

**Localize and Zoom.** When a high-severity event is flagged, Gemini scans the full frame and returns bounding box coordinates for hands and tools. The system crops the raw frame at those exact coordinates and re-queries Gemini on the zoomed crop. This forces the model to focus on the exact interaction zone rather than analyzing a wide spatially ambiguous shot. It directly solves the attention misallocation failure documented by AdaptVis (ICML 2025).

**Temporal consistency voting.** Rather than trusting a single frame, the system compares results across all frames within 2 seconds of the event. The majority vote confirms whether the event is real and sustained, filtering out one-frame anomalies and hallucinations.

**Evidence-grounded reporting.** The rule engine maps sidecar signals to named events: Near Miss, Idle Streak, Rework Proxy, Approach Hazard and Verification Moment. The claims in the final report is cited to a specific event ID and timestamp.

## Tech Stack

| Layer | Tools |
|-------|-------|
| Depth Estimation | MiDaS via torch.hub |
| Hand Tracking | MediaPipe |
| Object Detection | YOLOv8 |
| Spatial Query Loop | Gemini API |
| Backend | Python, OpenCV |
| Voice Agent | Jarvis, report-grounded LLM |

## Research Grounding

**[GeoMeter Benchmark](https://openaccess.thecvf.com/content/CVPR2025W/MMFM/papers/Azad_Understanding_Depth_and_Height_Perception_in_Large_Visual-Language_Models__CVPRW_2025_paper.pdf)** — Depth and height perception failures in SOTA VLMs. CVPRW 2025.

**[AdaptVis](https://arxiv.org/pdf/2503.01773)** — Attention misallocation in VLMs for spatial questions. ICML 2025.

**[LocVLM](https://arxiv.org/abs/2404.07449)** — Localization as a spatial reasoning bottleneck. CVPR 2024.

**[EgoConQS](https://www.sciencedirect.com/science/article/pii/S0926580524006691)** — Key activity queries for egocentric construction footage. Automation in Construction, 2025.

Built at Ironsite Hackathon.
