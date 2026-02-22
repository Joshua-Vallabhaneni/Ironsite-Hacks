import type {
  ParsedReport,
  VideoReport,
  ScoreSet,
  ClipEntry,
  EvidenceEntry,
  FrameEntry,
  ActivityTimelineEntry,
} from "./types";

export function parseReport(markdown: string): ParsedReport {
  // Extract date from title
  const titleMatch = markdown.match(
    /^# DAILY SITE REPORT — (\S+) — (.+)$/m
  );
  const date = titleMatch?.[1] ?? "";

  // Discover video filenames from PER-VIDEO BREAKDOWN section headers (source of truth)
  const breakdownFilenames = discoverVideoFilenames(markdown);

  // Fallback: also parse from title line in case PER-VIDEO BREAKDOWN is missing
  const titleFilenamesStr = titleMatch?.[2] ?? "";
  const titleFilenames = titleFilenamesStr.split(",").map((s) => s.trim()).filter(Boolean);

  // Use breakdown filenames as primary, fall back to title filenames
  const filenames = breakdownFilenames.length > 0 ? breakdownFilenames : titleFilenames;

  // Parse scores
  const scores = parseScoreboard(markdown);

  // Parse headlines
  const headlines = parseHeadlines(markdown);

  // Parse clips
  const clips = parseClips(markdown);

  // Parse narratives
  const safetyNarrative = extractSection(markdown, "## SAFETY DESK", "## ERGONOMICS");
  const ergonomicsNarrative = extractSection(markdown, "## ERGONOMICS", "## PRODUCTIVITY & FLOW");
  const productivityNarrative = extractProductivityNarrative(markdown);
  const qualityNarrative = extractSection(markdown, "## QUALITY & PROGRESS", "## PER-VIDEO BREAKDOWN");

  // Parse activity timeline
  const activityTimeline = parseActivityTimeline(markdown);

  // Parse per-video breakdown
  const videoBreakdowns = parsePerVideoBreakdown(markdown, filenames);

  // Parse audit trail
  const framesAnalyzed = parseFramesAnalyzed(markdown);
  const evidenceIndex = parseEvidenceIndex(markdown);

  // Build VideoReport for each video
  const videos: VideoReport[] = filenames.map((filename) => {
    const breakdown = videoBreakdowns.find((v) => v.filename === filename);

    // Filter per-video data from shared audit trail tables
    const videoFrames = framesAnalyzed.filter(
      (f) => f.videoFile === filename
    );
    const videoTimeline = activityTimeline.filter(
      (t) => t.video === filename
    );
    // Filter clips by event IDs that belong to this video's evidence
    const videoEvidenceIds = new Set(
      evidenceIndex
        .filter((e) => {
          // Match evidence to video via breakdown event list or frame data
          const matchingFrame = framesAnalyzed.find(
            (f) => f.videoFile === filename && f.timestamp === e.timestamp
          );
          return matchingFrame !== undefined;
        })
        .map((e) => e.eventId)
    );
    // If we can't attribute evidence to specific videos, give all evidence to each video
    // (single-video reports or when frame-to-evidence mapping isn't clear)
    const videoEvidence = videoEvidenceIds.size > 0
      ? evidenceIndex.filter((e) => videoEvidenceIds.has(e.eventId))
      : evidenceIndex;
    const videoClips = videoEvidenceIds.size > 0
      ? clips.filter((c) => videoEvidenceIds.has(c.eventId))
      : clips;

    return {
      filename,
      label: filename.replace(/\.mp4$/i, "").replace(/_/g, " "),
      duration: breakdown?.duration ?? "",
      resolution: breakdown?.resolution ?? "",
      eventsDetected: breakdown?.eventsDetected ?? 0,
      eventDistribution: breakdown?.eventDistribution ?? {},
      scores,
      headlines,
      clips: videoClips,
      safetyNarrative,
      ergonomicsNarrative,
      productivityNarrative,
      qualityNarrative,
      activityTimeline: videoTimeline.length > 0 ? videoTimeline : activityTimeline,
      evidenceIndex: videoEvidence,
      framesAnalyzed: videoFrames.length > 0 ? videoFrames : framesAnalyzed,
    };
  });

  return { date, videos };
}

/**
 * Discover video filenames by scanning ### headers inside ## PER-VIDEO BREAKDOWN.
 * This is the source of truth — one header per video that was analyzed.
 */
function discoverVideoFilenames(md: string): string[] {
  const breakdownStart = md.indexOf("## PER-VIDEO BREAKDOWN");
  if (breakdownStart === -1) return [];

  const auditStart = md.indexOf("## AUDIT TRAIL", breakdownStart);
  const breakdownSection = auditStart === -1
    ? md.slice(breakdownStart)
    : md.slice(breakdownStart, auditStart);

  const filenames: string[] = [];
  const headerRe = /^### (.+)$/gm;
  let m;
  while ((m = headerRe.exec(breakdownSection)) !== null) {
    const name = m[1].trim();
    if (name) filenames.push(name);
  }
  return filenames;
}

function parseScoreboard(md: string): ScoreSet {
  const tableMatch = md.match(
    /\|\s*(\d+(?:\.\d+)?)\/100\s*\|\s*(\d+(?:\.\d+)?)\/100\s*\|\s*(\d+(?:\.\d+)?)\/100\s*\|\s*(\d+(?:\.\d+)?)\/100\s*\|/
  );
  if (!tableMatch) return { safety: 0, ergonomics: 0, productivity: 0, quality: 0 };
  return {
    safety: parseFloat(tableMatch[1]),
    ergonomics: parseFloat(tableMatch[2]),
    productivity: parseFloat(tableMatch[3]),
    quality: parseFloat(tableMatch[4]),
  };
}

function parseHeadlines(md: string): string[] {
  const section = extractSection(md, "### Top Headlines", "### Scoreboard");
  const bullets: string[] = [];
  const lines = section.split("\n");
  for (const line of lines) {
    const m = line.match(/^\s*[\*\-]\s+(.+)/);
    if (m) bullets.push(m[1].trim());
  }
  return bullets.length > 0 ? bullets : [section.trim()].filter(Boolean);
}

function parseClips(md: string): ClipEntry[] {
  const section = extractSection(md, "### Must-Watch Clip Reel", "## SAFETY");
  const clips: ClipEntry[] = [];
  const re =
    /- \[(\S+) @ (\S+)\] — (.+?) \((\w+)\)(?: — \[clip\]\((.+?)\))?/g;
  let m;
  while ((m = re.exec(section)) !== null) {
    clips.push({
      eventId: m[1],
      timestamp: m[2],
      type: m[3],
      severity: m[4],
      clipPath: m[5] ?? "",
    });
  }
  return clips;
}

function extractSection(md: string, startMarker: string, endMarker: string): string {
  const startIdx = md.indexOf(startMarker);
  if (startIdx === -1) return "";
  const afterStart = startIdx + startMarker.length;
  const endIdx = md.indexOf(endMarker, afterStart);
  const text = endIdx === -1 ? md.slice(afterStart) : md.slice(afterStart, endIdx);
  return text.trim();
}

function extractProductivityNarrative(md: string): string {
  const section = extractSection(md, "## PRODUCTIVITY & FLOW", "## QUALITY & PROGRESS");
  // Remove the activity timeline table from the narrative
  const timelineIdx = section.indexOf("**Activity Timeline");
  if (timelineIdx === -1) return section;
  return section.slice(0, timelineIdx).trim();
}

function parseActivityTimeline(md: string): ActivityTimelineEntry[] {
  const section = extractSection(md, "**Activity Timeline (Gemini-labeled):**", "## QUALITY");
  const entries: ActivityTimelineEntry[] = [];
  const lines = section.split("\n");
  for (const line of lines) {
    const m = line.match(
      /\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|/
    );
    if (m && !m[1].startsWith("-") && m[1] !== "Video") {
      entries.push({
        video: m[1].trim(),
        timeRange: m[2].trim(),
        activity: m[3].trim(),
        tool: m[4].trim(),
        duration: m[5].trim(),
      });
    }
  }
  return entries;
}

interface VideoBreakdown {
  filename: string;
  duration: string;
  resolution: string;
  eventsDetected: number;
  eventDistribution: Record<string, number>;
}

function parsePerVideoBreakdown(md: string, filenames: string[]): VideoBreakdown[] {
  const results: VideoBreakdown[] = [];
  for (const filename of filenames) {
    const marker = `### ${filename}`;
    const startIdx = md.indexOf(marker);
    if (startIdx === -1) continue;
    const afterStart = startIdx + marker.length;
    // Find next ### or ## section
    const nextSection = md.slice(afterStart).search(/^##/m);
    const block = nextSection === -1 ? md.slice(afterStart) : md.slice(afterStart, afterStart + nextSection);

    const durMatch = block.match(/- Duration: (\S+)/);
    const resMatch = block.match(/- Resolution: (\S+)/);
    const evtMatch = block.match(/- Events detected: (\d+)/);

    const dist: Record<string, number> = {};
    const distRe = /  - (.+?): (\d+)/g;
    let dm;
    while ((dm = distRe.exec(block)) !== null) {
      // Only match distribution lines (not event detail lines with [@])
      if (!dm[0].includes("@")) {
        dist[dm[1]] = parseInt(dm[2]);
      }
    }

    results.push({
      filename,
      duration: durMatch?.[1] ?? "",
      resolution: resMatch?.[1] ?? "",
      eventsDetected: evtMatch ? parseInt(evtMatch[1]) : 0,
      eventDistribution: dist,
    });
  }
  return results;
}

function parseFramesAnalyzed(md: string): FrameEntry[] {
  const section = extractSection(md, "### Frames Analyzed", "### Evidence Index");
  const entries: FrameEntry[] = [];
  const lines = section.split("\n");
  for (const line of lines) {
    const m = line.match(
      /\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.*?)\s*\|/
    );
    if (m && !m[1].startsWith("-") && m[1] !== "Frame ID" && m[1] !== "...") {
      entries.push({
        frameId: m[1].trim(),
        videoFile: m[2].trim(),
        timestamp: m[3].trim(),
        reason: m[4].trim(),
        activityLabel: m[5].trim(),
      });
    }
  }
  return entries;
}

function parseEvidenceIndex(md: string): EvidenceEntry[] {
  const startIdx = md.indexOf("### Evidence Index");
  if (startIdx === -1) return [];
  const section = md.slice(startIdx);
  const entries: EvidenceEntry[] = [];
  const lines = section.split("\n");
  for (const line of lines) {
    const m = line.match(
      /\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|/
    );
    if (m && !m[1].startsWith("-") && m[1] !== "Claim") {
      entries.push({
        claim: m[1].trim(),
        eventId: m[2].trim(),
        timestamp: m[3].trim(),
        confidence: parseFloat(m[4].trim()),
      });
    }
  }
  return entries;
}
