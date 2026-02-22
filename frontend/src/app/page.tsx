"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  Download,
  Mic,
  Play,
  X,
  Phone,
  PhoneOff,
  Folder,
} from "lucide-react";
import { VideoUploadCard } from "@/components/ui/video-upload-card";
import { VoicePoweredOrb } from "@/components/ui/voice-powered-orb";
import { SAMPLE_REPORT } from "@/lib/sample-report";
import { useJarvisAgent, type JarvisState, type TranscriptMsg } from "@/hooks/useJarvisAgent";

/* ============================================================
   TYPES
   ============================================================ */
type Page = "upload" | "dashboard";

interface HardcodedClip {
  eventId: string;
  timestamp: string;
  type: string;
  severity: string;
  clipPath: string;
  confidence: number;
}

interface HardcodedVideo {
  tabLabel: string;
  source: string;
  duration: string;
  resolution: string;
  eventsDetected: number;
  scores: { safety: number; ergonomics: number; productivity: number; quality: number };
  clips: HardcodedClip[];
}

/* ============================================================
   HARDCODED VIDEO DATA — all values from SAMPLE_REPORT
   ============================================================ */
const VIDEOS: HardcodedVideo[] = [
  {
    tabLabel: "02 Production Masonry",
    source: "02_production_masonry.mp4",
    duration: "00:21:16",
    resolution: "640x480",
    eventsDetected: 11,
    scores: { safety: 35, ergonomics: 85, productivity: 50.9, quality: 75 },
    clips: [
      { eventId: "approach_hazard_proxy_1c2b62", timestamp: "00:11:56", type: "Approach Hazard Proxy", severity: "med", clipPath: "/ConstructionData/vid2Data/vid2-approachhazard.mp4", confidence: 0.80 },
      { eventId: "ppe_violation_b01500", timestamp: "00:04:29", type: "Ppe Violation", severity: "high", clipPath: "/ConstructionData/vid2Data/vid2-ppe.mp4", confidence: 0.75 },
      { eventId: "verification_moment_b89e43", timestamp: "00:04:00", type: "Verification Moment", severity: "low", clipPath: "/ConstructionData/vid2Data/vid2-verification.mp4", confidence: 0.70 },
      { eventId: "ppe_violation_007241", timestamp: "00:05:30", type: "Ppe Violation", severity: "high", clipPath: "/ConstructionData/vid2Data/vid2Clips/ppe_violation_007241.mp4", confidence: 0.80 },
      { eventId: "ppe_violation_fab518", timestamp: "00:18:40", type: "Ppe Violation", severity: "high", clipPath: "/ConstructionData/vid2Data/vid2Clips/ppe_violation_fab518.mp4", confidence: 0.75 },
      { eventId: "rework_proxy_34fab6", timestamp: "00:04:31", type: "Rework Proxy", severity: "med", clipPath: "/ConstructionData/vid2Data/vid2Clips/rework_proxy_34fab6.mp4", confidence: 0.85 },
      { eventId: "rework_proxy_379d49", timestamp: "00:06:08", type: "Rework Proxy", severity: "med", clipPath: "/ConstructionData/vid2Data/vid2Clips/rework_proxy_379d49.mp4", confidence: 0.70 },
      { eventId: "rework_proxy_b4e63f", timestamp: "00:04:29", type: "Rework Proxy", severity: "med", clipPath: "/ConstructionData/vid2Data/vid2Clips/rework_proxy_b4e63f.mp4", confidence: 0.85 },
      { eventId: "task_transition_729d1a", timestamp: "00:04:33", type: "Task Transition", severity: "low", clipPath: "/ConstructionData/vid2Data/vid2Clips/task_transition_729d1a.mp4", confidence: 0.85 },
      { eventId: "task_transition_75f57a", timestamp: "00:19:13", type: "Task Transition", severity: "low", clipPath: "/ConstructionData/vid2Data/vid2Clips/task_transition_75f57a.mp4", confidence: 0.75 },
      { eventId: "task_transition_c79480", timestamp: "00:20:44", type: "Task Transition", severity: "low", clipPath: "/ConstructionData/vid2Data/vid2Clips/task_transition_c79480.mp4", confidence: 0.90 },
    ],
  },
  {
    tabLabel: "03 Production Masonry",
    source: "03_production_masonry.mp4",
    duration: "00:21:16",
    resolution: "640x480",
    eventsDetected: 33,
    scores: { safety: 0, ergonomics: 80, productivity: 49.3, quality: 80 },
    clips: [
      { eventId: "idle_streak_a602a2", timestamp: "00:00:35", type: "Idle Streak", severity: "low", clipPath: "/ConstructionData/vid3Data/vid3-idle.mp4", confidence: 0.80 },
      { eventId: "ppe_violation_42553b", timestamp: "00:00:58", type: "Ppe Violation", severity: "high", clipPath: "/ConstructionData/vid3Data/vid3-ppe.mp4", confidence: 0.85 },
      { eventId: "idle_streak_ca30f2", timestamp: "00:01:38", type: "Idle Streak", severity: "low", clipPath: "/ConstructionData/vid3Data/vid3clips/idle_streak_ca30f2.mp4", confidence: 0.80 },
      { eventId: "ppe_violation_ba73f6", timestamp: "00:10:02", type: "Ppe Violation", severity: "high", clipPath: "/ConstructionData/vid3Data/vid3clips/ppe_violation_ba73f6.mp4", confidence: 0.85 },
      { eventId: "ppe_violation_c888cd", timestamp: "00:01:29", type: "Ppe Violation", severity: "high", clipPath: "/ConstructionData/vid3Data/vid3clips/ppe_violation_c888cd.mp4", confidence: 0.80 },
      { eventId: "task_transition_68ffb2", timestamp: "00:12:08", type: "Task Transition", severity: "low", clipPath: "/ConstructionData/vid3Data/vid3clips/task_transition_68ffb2.mp4", confidence: 0.75 },
      { eventId: "task_transition_b61394", timestamp: "00:10:07", type: "Task Transition", severity: "low", clipPath: "/ConstructionData/vid3Data/vid3clips/task_transition_b61394.mp4", confidence: 0.85 },
      { eventId: "verification_moment_07ab17", timestamp: "00:15:38", type: "Verification Moment", severity: "low", clipPath: "/ConstructionData/vid3Data/vid3clips/verification_moment_07ab17.mp4", confidence: 0.70 },
      { eventId: "verification_moment_314892", timestamp: "00:21:12", type: "Verification Moment", severity: "low", clipPath: "/ConstructionData/vid3Data/vid3clips/verification_moment_314892.mp4", confidence: 0.70 },
      { eventId: "verification_moment_92ddd9", timestamp: "00:09:06", type: "Verification Moment", severity: "low", clipPath: "/ConstructionData/vid3Data/vid3clips/verification_moment_92ddd9.mp4", confidence: 0.70 },
      { eventId: "verification_moment_ff5ed4", timestamp: "00:00:00", type: "Verification Moment", severity: "low", clipPath: "/ConstructionData/vid3Data/vid3clips/verification_moment_ff5ed4.mp4", confidence: 0.70 },
    ],
  },
  {
    tabLabel: "05 Production MP",
    source: "05_production_mp.mp4",
    duration: "00:20:12",
    resolution: "820x616",
    eventsDetected: 12,
    scores: { safety: 80, ergonomics: 70, productivity: 52.1, quality: 45 },
    clips: [
      { eventId: "rework_proxy_a60089", timestamp: "00:01:31", type: "Rework Proxy", severity: "med", clipPath: "/ConstructionData/vid5Data/vid5-rework.mp4", confidence: 0.90 },
      { eventId: "task_transition_c14298", timestamp: "00:05:30", type: "Task Transition", severity: "low", clipPath: "/ConstructionData/vid5Data/vid5-task-trans.mp4", confidence: 0.80 },
      { eventId: "verification_moment_e6aa6f", timestamp: "00:20:00", type: "Verification Moment", severity: "low", clipPath: "/ConstructionData/vid5Data/vid5-verify.mp4", confidence: 0.75 },
      { eventId: "ppe_violation_700e6b", timestamp: "00:19:58", type: "Ppe Violation", severity: "high", clipPath: "/ConstructionData/vid5Data/vid5-clips/ppe_violation_700e6b.mp4", confidence: 0.75 },
      { eventId: "rework_proxy_001777", timestamp: "00:12:15", type: "Rework Proxy", severity: "med", clipPath: "/ConstructionData/vid5Data/vid5-clips/rework_proxy_001777.mp4", confidence: 0.93 },
      { eventId: "rework_proxy_141975", timestamp: "00:07:42", type: "Rework Proxy", severity: "med", clipPath: "/ConstructionData/vid5Data/vid5-clips/rework_proxy_141975.mp4", confidence: 0.80 },
      { eventId: "rework_proxy_567d85", timestamp: "00:06:42", type: "Rework Proxy", severity: "med", clipPath: "/ConstructionData/vid5Data/vid5-clips/rework_proxy_567d85.mp4", confidence: 0.90 },
      { eventId: "rework_proxy_b150f8", timestamp: "00:06:48", type: "Rework Proxy", severity: "med", clipPath: "/ConstructionData/vid5Data/vid5-clips/rework_proxy_b150f8.mp4", confidence: 0.85 },
      { eventId: "rework_proxy_c0407f", timestamp: "00:06:43", type: "Rework Proxy", severity: "med", clipPath: "/ConstructionData/vid5Data/vid5-clips/rework_proxy_c0407f.mp4", confidence: 0.90 },
      { eventId: "task_transition_21dff7", timestamp: "00:16:30", type: "Task Transition", severity: "low", clipPath: "/ConstructionData/vid5Data/vid5-clips/task_transition_21dff7.mp4", confidence: 0.95 },
      { eventId: "task_transition_2c812c", timestamp: "00:15:00", type: "Task Transition", severity: "low", clipPath: "/ConstructionData/vid5Data/vid5-clips/task_transition_2c812c.mp4", confidence: 0.93 },
      { eventId: "task_transition_befcd7", timestamp: "00:14:00", type: "Task Transition", severity: "low", clipPath: "/ConstructionData/vid5Data/vid5-clips/task_transition_befcd7.mp4", confidence: 0.75 },
    ],
  },
];

const REPORT_DATE = "2026-02-22";

/* ============================================================
   UTILITY
   ============================================================ */
function getScoreColor(score: number): string {
  if (score >= 80) return "#22c55e";
  if (score >= 50) return "#f59e0b";
  return "#ef4444";
}

function getSeverityBorder(severity: string): string {
  if (severity === "high") return "#ef4444";
  if (severity === "med") return "#f59e0b";
  return "#3b82f6";
}

function getSeverityGlow(severity: string): string {
  if (severity === "high") return "0 0 24px rgba(239,68,68,0.25)";
  if (severity === "med") return "0 0 24px rgba(245,158,11,0.25)";
  return "0 0 24px rgba(59,130,246,0.25)";
}

function getSeverityBg(severity: string): string {
  if (severity === "high") return "bg-[#ef4444]";
  if (severity === "med") return "bg-[#f59e0b]";
  return "bg-[#3b82f6]";
}

function getSeverityBadge(severity: string): string {
  if (severity === "high") return "bg-[rgba(239,68,68,0.15)] text-[#ef4444]";
  if (severity === "med") return "bg-[rgba(245,158,11,0.15)] text-[#f59e0b]";
  return "bg-[rgba(59,130,246,0.15)] text-[#3b82f6]";
}

function thumbGradient(idx: number): string {
  const hues = [210, 190, 230, 170, 250];
  const h = hues[idx % hues.length];
  return `linear-gradient(135deg, hsl(${h},40%,18%) 0%, hsl(${h + 30},35%,12%) 50%, hsl(${h - 10},45%,8%) 100%)`;
}

/* ============================================================
   COMPONENT: Skeleton
   ============================================================ */
function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} />;
}

/* ============================================================
   COMPONENT: LightboxModal
   ============================================================ */
function LightboxModal({ clip, onClose }: { clip: HardcodedClip; onClose: () => void }) {
  return (
    <div className="lightbox-overlay" onClick={onClose}>
      <div className="lightbox-content" onClick={(e) => e.stopPropagation()}>
        <button className="lightbox-close" onClick={onClose}>
          <X className="h-5 w-5" />
        </button>
        <div className="rounded-lg overflow-hidden bg-black aspect-video flex items-center justify-center">
          <video key={clip.clipPath} controls autoPlay muted playsInline preload="auto" className="w-full h-full" src={clip.clipPath} />
        </div>
        <div className="mt-4 space-y-2">
          <div className="flex items-center gap-3">
            <span className={`text-[12px] font-bold px-2.5 py-1 rounded-md ${getSeverityBadge(clip.severity)}`}>
              {clip.severity}
            </span>
            <span className="text-[15px] font-semibold text-[#E5E5E5]">{clip.type}</span>
          </div>
          <div className="flex items-center gap-3 text-[12px] text-[#666] flex-wrap">
            <span className="font-mono text-[#888]">{clip.eventId}</span>
            <span className="text-[#444]">&middot;</span>
            <span className="font-mono">{clip.timestamp}</span>
            <span className="text-[#444]">&middot;</span>
            <span>{clip.type}</span>
            <span className="text-[#444]">&middot;</span>
            <span>{clip.severity}</span>
            <span className="text-[#444]">&middot;</span>
            <span>confidence {clip.confidence.toFixed(2)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   COMPONENT: LazyVideo — loads video src only when visible
   ============================================================ */
function LazyVideo({ src, delay = 0 }: { src: string; delay?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const [loadSrc, setLoadSrc] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setTimeout(() => setLoadSrc(true), delay);
          observer.disconnect();
        }
      },
      { rootMargin: "200px" }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [delay]);

  return (
    <div ref={ref} className="absolute inset-0 w-full h-full">
      {loadSrc && (
        <video
          src={src}
          muted
          preload="metadata"
          playsInline
          className="w-full h-full object-cover"
          onLoadedData={(e) => { (e.currentTarget as HTMLVideoElement).currentTime = 1; }}
        />
      )}
    </div>
  );
}

/* ============================================================
   COMPONENT: MustWatchClips
   ============================================================ */
function MustWatchClips({ clips }: { clips: HardcodedClip[] }) {
  const [lightboxClip, setLightboxClip] = useState<HardcodedClip | null>(null);

  if (clips.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-[15px] text-[#555] italic">No clips available for this video</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5 flex-1">
      <h3 className="text-[18px] font-semibold text-[#E5E5E5]">Must-Watch Clips</h3>

      {/* Scrollable grid container */}
      <div className="clips-scroll-container">
        <div className={`grid gap-8 ${clips.length <= 2 ? "grid-cols-2" : "grid-cols-3"}`}>
          {clips.map((clip, i) => (
            <div
              key={i}
              className="clip-card group"
              style={{ border: `1.5px solid ${getSeverityBorder(clip.severity)}` }}
              onClick={() => setLightboxClip(clip)}
              onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.boxShadow = getSeverityGlow(clip.severity); }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.boxShadow = "none"; }}
            >
              {/* Lazy-loaded video thumbnail */}
              <LazyVideo src={clip.clipPath} delay={i * 100} />
              <div className="clip-gradient" />

              <div className="absolute bottom-3 left-3 right-3 z-10">
                <p className="text-[14px] font-semibold text-white leading-snug">{clip.type}</p>
                <span className="text-[11px] font-mono text-white/50 mt-1 inline-block">{clip.timestamp}</span>
              </div>

              <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-300 z-10">
                <div className="w-12 h-12 rounded-full bg-white/15 backdrop-blur-md flex items-center justify-center">
                  <Play className="h-5 w-5 text-white ml-0.5" />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {lightboxClip && (
        <LightboxModal clip={lightboxClip} onClose={() => setLightboxClip(null)} />
      )}
    </div>
  );
}

/* ============================================================
   PDF Download
   ============================================================ */
function downloadReportPDF(_video: HardcodedVideo) {
  const a = document.createElement("a");
  a.href = "/combined_daily_site_report_2026-02-22_structured_plain.pdf";
  a.download = "combined_daily_site_report_2026-02-22.pdf";
  a.click();
}

/* ============================================================
   MAIN PAGE
   ============================================================ */
export default function Home() {
  const [page, setPage] = useState<Page>("upload");
  const [selectedVideoIndex, setSelectedVideoIndex] = useState(0);

  const [dashboardLoaded, setDashboardLoaded] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [processStep, setProcessStep] = useState(-1);
  const transcriptEndRef = useRef<HTMLDivElement>(null);

  // ElevenLabs voice agent hook
  const {
    jarvisState,
    transcripts,
    setTranscripts,
    addMsg,
    status: agentStatus,
    startSession,
    endSession,
    sendContextualUpdate,
  } = useJarvisAgent(false);

  useEffect(() => { transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [transcripts]);

  useEffect(() => {
    setDashboardLoaded(false);
    const t = setTimeout(() => setDashboardLoaded(true), 800);
    return () => clearTimeout(t);
  }, [selectedVideoIndex]);

  /* ---------- Screen Context Builder ---------- */
  const buildScreenContext = useCallback((videoIndex: number): string => {
    const video = VIDEOS[videoIndex];
    return [
      `SCREEN_CONTEXT:`,
      `Report: ${REPORT_DATE}, Video: ${video.source}, Duration: ${video.duration}`,
      `Worker: Marcus Rivera, Site: #4`,
      `Scoreboard: Safety ${video.scores.safety}/100, Ergonomics ${video.scores.ergonomics}/100, Productivity ${video.scores.productivity}/100, Quality ${video.scores.quality}/100`,
      `Events Detected: ${video.eventsDetected}`,
      `Clips on screen:`,
      ...video.clips.map(c => `  - ${c.timestamp} | ${c.type} (${c.severity} severity) - Confidence: ${(c.confidence * 100).toFixed(0)}%`)
    ].join("\n");
  }, []);

  /* ---------- Send context on dashboard entry or video change ---------- */
  useEffect(() => {
    if (page === "dashboard" && agentStatus === "connected") {
      const ctx = buildScreenContext(selectedVideoIndex);
      sendContextualUpdate(ctx);
    }
  }, [page, agentStatus, selectedVideoIndex, buildScreenContext, sendContextualUpdate]);


  /* ---------- Processing Simulation ---------- */
  const startProcessing = useCallback(() => {
    setProcessing(true);

    const steps = [
      { msg: "Uploading footage... complete.", delay: 1200 },
      { msg: "Running spatial depth analysis...", delay: 2000 },
      { msg: "Tracking hand and tool interactions...", delay: 2500 },
      { msg: "Generating your performance report...", delay: 2000 },
    ];

    let cumulative = 0;
    steps.forEach((s, i) => {
      cumulative += s.delay;
      setTimeout(() => {
        setProcessStep(i);
        addMsg(s.msg, "jarvis");
      }, cumulative);
    });

    cumulative += 2000;
    setTimeout(() => {
      setProcessStep(4);
      addMsg("Analysis complete. Transitioning to your dashboard...", "jarvis");
      setTimeout(() => {
        setPage("dashboard");
        setProcessing(false);
        setProcessStep(-1);
        setTranscripts((prev) => [
          ...prev,
          {
            id: Date.now(),
            text: "Analysis complete. Today's report is ready. I've identified key quality and productivity insights. Click Start Conversation to discuss the findings with me.",
            sender: "jarvis",
          },
        ]);
      }, 1200);
    }, cumulative);
  }, [addMsg, setTranscripts]);

  const switchVideo = (index: number) => {
    setSelectedVideoIndex(index);
    if (agentStatus !== "connected") {
      addMsg(`Switching to ${VIDEOS[index].tabLabel}. Loading report data...`, "jarvis");
    }
  };

  const currentVideo = VIDEOS[selectedVideoIndex];
  const scores = currentVideo.scores;

  /* ---------- JARVIS Panel ---------- */
  const JarvisPanel = () => (
    <div className="jarvis-panel w-full md:w-72 lg:w-80 flex flex-col items-center py-8 px-6 h-full relative z-10">
      {/* MIDDLE: title + orb + waveform + transcript — grows to fill available space */}
      <div className="flex-1 flex flex-col items-center w-full min-h-0">
        <h1 className="text-lg font-bold tracking-widest text-[#06b6d4] uppercase">JARVIS</h1>
        <p className="text-[0.6rem] text-[#6b7f99] tracking-[0.25em] uppercase mt-0.5 mb-2">Intelligent Jobsite Oversight</p>
        <div className="orb-glow w-44 h-44 my-6 p-5 flex-shrink-0">
          <VoicePoweredOrb enableVoiceControl={false} hue={0} className="w-full h-full" />
        </div>
        <div className={`waveform ${jarvisState === "speaking" ? "active" : jarvisState === "listening" ? "listening" : ""}`}>
          {Array.from({ length: 40 }).map((_, i) => {
            const seed1 = ((i * 7 + 3) % 13) / 13;
            const seed2 = ((i * 11 + 5) % 17) / 17;
            const seed3 = ((i * 13 + 7) % 19) / 19;
            return <div key={i} className="bar" style={{ height: `${4 + seed1 * 12}px`, animationDelay: `${seed2 * 0.5}s`, ["--max-h" as string]: `${8 + seed3 * 14}px` }} />;
          })}
        </div>
        <div className="mt-3 text-[0.65rem] tracking-[0.2em] uppercase text-[#6b7f99] flex items-center gap-1">
          <span className={`pulse-dot ${jarvisState === "speaking" ? "speaking" : jarvisState === "listening" ? "listening" : "standby"}`} />
          {agentStatus === "connected" ? (jarvisState === "speaking" ? "JARVIS IS SPEAKING..." : "LISTENING...") : "STANDBY"}
        </div>
        <div className="w-full flex-1 mt-6 overflow-y-auto max-h-52 space-y-2 pr-2 custom-scrollbar">
          {transcripts.map((msg) => <div key={msg.id} className={`transcript-bubble ${msg.sender}`}>{msg.text}</div>)}
          <div ref={transcriptEndRef} />
        </div>

        {page === "dashboard" && (
          <div className="flex flex-col items-center gap-3 mt-6">
            {agentStatus === "connected" ? (
              <button
                className="mic-btn active"
                onClick={endSession}
              >
                <PhoneOff className="h-4 w-4 mr-2 inline-block" />
                End Conversation
              </button>
            ) : (
              <button
                className="mic-btn"
                onClick={startSession}
              >
                <Phone className="h-4 w-4 mr-2 inline-block" />
                Start Conversation
              </button>
            )}
            {agentStatus === "connected" && (
              <p className="text-[0.6rem] text-emerald-400 tracking-widest uppercase flex items-center gap-1 mt-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Live — Just speak naturally
              </p>
            )}
          </div>
        )}

        <div className="mt-auto pt-6 text-center">
          <p className="text-[0.65rem] text-[#6b7f99]">{REPORT_DATE}</p>
        </div>
      </div>
    </div>
  );

  /* ---------- DASHBOARD (Sub-components) ---------- */
  const ContentSkeleton = () => (
    <div className="space-y-4 p-6">
      <Skeleton className="h-5 w-48 mb-4" />
      <Skeleton className="h-[280px] w-full" />
      <div className="grid grid-cols-3 gap-4">
        <Skeleton className="aspect-video" />
        <Skeleton className="aspect-video" />
        <Skeleton className="aspect-video" />
      </div>
    </div>
  );

  /* ---------- UPLOAD PAGE ---------- */
  if (page === "upload") {
    return (
      <main className="h-screen flex flex-col items-center justify-center relative overflow-hidden">
        <div className="bg-grid" />
        <div className="scanlines" />

        <div className="relative z-10 flex flex-col items-center w-full max-w-2xl px-8">
          <div className="flex flex-col items-center mb-10">
            <h1 className="text-lg font-bold tracking-widest text-[#06b6d4] uppercase">
              JARVIS
            </h1>
            <p className="text-[0.6rem] text-[#6b7f99] tracking-[0.25em] uppercase mt-0.5">
              Intelligent Jobsite Oversight
            </p>

            <div className="orb-glow w-36 h-36 my-6">
              <VoicePoweredOrb
                enableVoiceControl={false}
                hue={0}
                className="w-full h-full"
              />
            </div>

            <div className={`waveform ${jarvisState === "speaking" ? "active" : jarvisState === "listening" ? "listening" : ""}`}>
              {Array.from({ length: 40 }).map((_, i) => {
                const seed1 = ((i * 7 + 3) % 13) / 13;
                const seed2 = ((i * 11 + 5) % 17) / 17;
                const seed3 = ((i * 13 + 7) % 19) / 19;
                return (
                  <div
                    key={i}
                    className="bar"
                    style={{
                      height: `${4 + seed1 * 12}px`,
                      animationDelay: `${seed2 * 0.5}s`,
                      ["--max-h" as string]: `${8 + seed3 * 14}px`,
                    }}
                  />
                );
              })}
            </div>

            <div className="mt-3 text-[0.65rem] tracking-[0.2em] uppercase text-[#6b7f99] flex items-center gap-1">
              <span className={`pulse-dot ${jarvisState === "speaking" ? "speaking" : jarvisState === "listening" ? "listening" : "standby"}`} />
              {jarvisState === "speaking" ? "JARVIS IS SPEAKING..." : jarvisState === "listening" ? "LISTENING..." : "STANDBY"}
            </div>

            <div className="w-full max-w-md mt-4 space-y-2">
              {transcripts.slice(-2).map((msg) => (
                <div key={msg.id} className={`transcript-bubble ${msg.sender}`}>
                  {msg.text}
                </div>
              ))}
            </div>
          </div>

          {!processing ? (
            <VideoUploadCard
              title="Upload Headcam Footage"
              description="Drop your video files here to begin AI-powered site analysis."
              className="w-full"
              onFileSelected={() => startProcessing()}
            />
          ) : (
            <div className="w-full max-w-xl">
              <p className="text-sm text-[#c8d6e5] text-center mb-8">
                Analyzing footage...
              </p>
              <div className="flex items-center justify-between">
                {["Upload", "Process", "Analyze", "Report"].map((label, i) => (
                  <div key={label} className="flex items-center flex-1 last:flex-initial">
                    <div className="flex flex-col items-center">
                      <div
                        className={`progress-step ${processStep === i ? "active" : processStep > i ? "done" : ""}`}
                      >
                        <div className="step-dot">
                          {processStep > i ? "✓" : i + 1}
                        </div>
                      </div>
                      <span
                        className={`text-[0.7rem] mt-2 ${processStep >= i ? "text-[#c8d6e5]" : "text-[#6b7f99]"}`}
                      >
                        {label}
                      </span>
                    </div>
                    {i < 3 && (
                      <div
                        className={`flex-1 h-px mx-3 mb-5 ${processStep > i
                          ? "bg-[rgba(6,182,212,0.4)]"
                          : "bg-[rgba(56,139,255,0.1)]"
                          }`}
                      />
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </main>
    );
  }

  return (
    <main className="h-screen flex relative overflow-hidden">
      <div className="bg-grid" /><div className="scanlines" />
      <aside className="hidden md:flex flex-col h-screen sticky top-0"><JarvisPanel /></aside>

      <div className="flex-1 relative z-10 overflow-y-auto h-screen flex flex-col">
        <div className="py-8 flex-1 flex flex-col" style={{ paddingLeft: "32px", paddingRight: "32px" }}>
          {/* Video Selector Tab Bar — with Download Reports button */}
          <div className="video-tab-bar" style={{ justifyContent: "space-between" }}>
            <div className="flex">
              {VIDEOS.map((v, i) => (
                <button
                  key={i}
                  className={`video-tab-item ${selectedVideoIndex === i ? "active" : ""}`}
                  onClick={() => switchVideo(i)}
                >
                  <span>{v.tabLabel}</span>
                  <span className="video-tab-duration">{v.duration}</span>
                  {selectedVideoIndex === i && <div className="video-tab-underline" />}
                </button>
              ))}
            </div>
            <div className="flex items-center pr-2 pb-1">
              <button className="ghost-btn" onClick={() => downloadReportPDF(currentVideo)}>
                <Download className="h-3.5 w-3.5" /> Download Report
              </button>
            </div>
          </div>

          {/* Score Cards */}
          {dashboardLoaded && (
            <div className="grid grid-cols-4 gap-4 mb-12">
              {(["safety", "ergonomics", "productivity", "quality"] as const).map((key) => {
                const val = scores[key];
                const color = getScoreColor(val);
                const label = key.charAt(0).toUpperCase() + key.slice(1);
                const radius = 36;
                const circumference = 2 * Math.PI * radius;
                const offset = circumference - (val / 100) * circumference;
                return (
                  <div key={key} className="score-tile">
                    <svg width="88" height="88" viewBox="0 0 88 88">
                      <circle cx="44" cy="44" r={radius} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="6" />
                      <circle
                        cx="44" cy="44" r={radius} fill="none"
                        stroke={color} strokeWidth="6" strokeLinecap="round"
                        strokeDasharray={circumference} strokeDashoffset={offset}
                        transform="rotate(-90 44 44)"
                        style={{ transition: "stroke-dashoffset 0.8s ease" }}
                      />
                      <text x="44" y="48" textAnchor="middle" fill={color} fontSize="18" fontWeight="700" fontFamily="Inter, sans-serif">
                        {val}
                      </text>
                    </svg>
                    <span className="text-[12px] text-[#888] mt-2 uppercase tracking-wider font-medium">{label}</span>
                  </div>
                );
              })}
            </div>
          )}

          {/* Clips Content */}
          <div key={selectedVideoIndex} className="tab-content-fade flex-1 flex flex-col">
            {!dashboardLoaded ? <ContentSkeleton /> : (
              <div className="flex-1 flex flex-col">
                <MustWatchClips clips={currentVideo.clips} />
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
