"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  Download,
  Mic,
  Play,
  X,
} from "lucide-react";
import { VoicePoweredOrb } from "@/components/ui/voice-powered-orb";
import { SAMPLE_REPORT } from "@/lib/sample-report";

/* ============================================================
   TYPES
   ============================================================ */
type JarvisState = "idle" | "speaking" | "listening";

interface TranscriptMsg {
  id: number;
  text: string;
  sender: "jarvis" | "user";
}

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
          <video key={clip.clipPath} controls autoPlay playsInline preload="auto" className="w-full h-full" src={clip.clipPath} />
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

      {/* Uniform grid — all clips same size */}
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
            {/* Video thumbnail */}
            <video
              src={clip.clipPath}
              muted
              preload="metadata"
              playsInline
              className="absolute inset-0 w-full h-full object-cover"
              onLoadedData={(e) => { (e.currentTarget as HTMLVideoElement).currentTime = 1; }}
            />
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
  const page = "dashboard";
  const [selectedVideoIndex, setSelectedVideoIndex] = useState(0);
  const [jarvisState, setJarvisState] = useState<JarvisState>("speaking");
  const [transcripts, setTranscripts] = useState<TranscriptMsg[]>([
    { id: 1, text: "Analysis complete. Today's report is ready. I've identified key quality and productivity insights. Shall I walk you through the highlights?", sender: "jarvis" },
  ]);
  const [holding, setHolding] = useState(false);
  const [dashboardLoaded, setDashboardLoaded] = useState(false);
  const transcriptEndRef = useRef<HTMLDivElement>(null);
  const msgIdRef = useRef(2);

  useEffect(() => { transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [transcripts]);
  useEffect(() => { const t = setTimeout(() => setJarvisState("idle"), 4000); return () => clearTimeout(t); }, []);

  useEffect(() => {
    setDashboardLoaded(false);
    const t = setTimeout(() => setDashboardLoaded(true), 800);
    return () => clearTimeout(t);
  }, [selectedVideoIndex]);

  const addMsg = useCallback((text: string, sender: "jarvis" | "user") => {
    setTranscripts((prev) => {
      const next = [...prev, { id: msgIdRef.current++, text, sender }];
      return next.slice(-6);
    });
  }, []);

  const handleMicDown = () => { setHolding(true); setJarvisState("listening"); };
  const handleMicUp = () => {
    if (!holding) return;
    setHolding(false);
    addMsg("Can you tell me more about the quality findings?", "user");
    setTimeout(() => {
      setJarvisState("speaking");
      addMsg("Of course. Today I detected verification moments and rework proxy events across the videos. The rework events suggest workers returned to completed areas multiple times, which may indicate corrections were needed.", "jarvis");
      setTimeout(() => setJarvisState("idle"), 5000);
    }, 1000);
  };

  const switchVideo = (index: number) => {
    setSelectedVideoIndex(index);
    setJarvisState("speaking");
    addMsg(`Switching to ${VIDEOS[index].tabLabel}. Loading report data...`, "jarvis");
    setTimeout(() => setJarvisState("idle"), 2000);
  };

  const currentVideo = VIDEOS[selectedVideoIndex];
  const scores = currentVideo.scores;

  /* ---------- JARVIS Panel (shared, UNTOUCHED) ---------- */
  const JarvisPanel = () => (
    <div className="jarvis-panel w-full md:w-72 lg:w-80 flex flex-col items-center py-8 px-6 h-full relative z-10">
      {/* MIDDLE: title + orb + waveform + transcript — grows to fill available space */}
      <div className="flex-1 flex flex-col items-center w-full min-h-0">
        <h1 className="text-lg font-bold tracking-widest text-[#06b6d4] uppercase">JARVIS</h1>
        <p className="text-[0.6rem] text-[#6b7f99] tracking-[0.25em] uppercase mt-0.5 mb-2">Intelligent Jobsite Oversight</p>
        <div className="orb-glow w-44 h-44 my-6 p-5 flex-shrink-0">
          <VoicePoweredOrb enableVoiceControl={false} hue={0} className="w-full h-full" />
        </div>
        <div className={`waveform flex-shrink-0 ${jarvisState === "speaking" ? "active" : jarvisState === "listening" ? "listening" : ""}`}>
          {Array.from({ length: 40 }).map((_, i) => {
            const seed1 = ((i * 7 + 3) % 13) / 13;
            const seed2 = ((i * 11 + 5) % 17) / 17;
            const seed3 = ((i * 13 + 7) % 19) / 19;
            return <div key={i} className="bar" style={{ height: `${4 + seed1 * 12}px`, animationDelay: `${seed2 * 0.5}s`, ["--max-h" as string]: `${8 + seed3 * 14}px` }} />;
          })}
        </div>
        <div className="mt-3 flex-shrink-0 text-[0.65rem] tracking-[0.2em] uppercase text-[#6b7f99] flex items-center gap-1">
          <span className={`pulse-dot ${jarvisState === "speaking" ? "speaking" : jarvisState === "listening" ? "listening" : "standby"}`} />
          {jarvisState === "speaking" ? "JARVIS IS SPEAKING..." : jarvisState === "listening" ? "LISTENING..." : "STANDBY"}
        </div>
        <div className="w-full mt-4 flex-1 min-h-0 overflow-y-auto space-y-2">
          {transcripts.map((msg) => <div key={msg.id} className={`transcript-bubble ${msg.sender}`}>{msg.text}</div>)}
          <div ref={transcriptEndRef} />
        </div>
      </div>

      {/* BOTTOM: mic button + date — always pinned to bottom */}
      <div className="w-full flex flex-col items-center gap-4 pt-4">
        {page === "dashboard" && (
          <button className={`mic-btn w-full justify-center ${holding ? "active" : ""}`} onMouseDown={handleMicDown} onMouseUp={handleMicUp} onMouseLeave={() => holding && handleMicUp()}>
            <Mic className="h-4 w-4" /> Hold to Speak
          </button>
        )}
        <div className="text-center">
          <p className="text-[0.65rem] text-[#6b7f99]">{REPORT_DATE}</p>
          <p className="text-[0.7rem] text-[#c8d6e5] mt-1 flex items-center gap-1.5 justify-center">
            <span className="w-1.5 h-1.5 rounded-full bg-green-400" /> Worker &middot; Site #4
          </p>
        </div>
      </div>
    </div>
  );

  /* ---------- DASHBOARD ---------- */
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
