export interface ParsedReport {
  date: string;
  videos: VideoReport[];
}

export interface VideoReport {
  filename: string;
  label: string;
  duration: string;
  resolution: string;
  eventsDetected: number;
  eventDistribution: Record<string, number>;
  scores: ScoreSet;
  headlines: string[];
  clips: ClipEntry[];
  safetyNarrative: string;
  ergonomicsNarrative: string;
  productivityNarrative: string;
  qualityNarrative: string;
  activityTimeline: ActivityTimelineEntry[];
  evidenceIndex: EvidenceEntry[];
  framesAnalyzed: FrameEntry[];
}

export interface ScoreSet {
  safety: number;
  ergonomics: number;
  productivity: number;
  quality: number;
}

export interface ClipEntry {
  eventId: string;
  timestamp: string;
  type: string;
  severity: string;
  clipPath: string;
  confidence: number;
}

export interface EvidenceEntry {
  claim: string;
  eventId: string;
  timestamp: string;
  confidence: number;
}

export interface FrameEntry {
  frameId: string;
  videoFile: string;
  timestamp: string;
  reason: string;
  activityLabel: string;
}

export interface ActivityTimelineEntry {
  video: string;
  timeRange: string;
  activity: string;
  tool: string;
  duration: string;
}
