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
import { useJarvisAgent, type JarvisState, type TranscriptMsg } from "@/hooks/useJarvisAgent";
import { parseReport } from "@/lib/parse-report";
import type { ParsedReport, ClipEntry } from "@/lib/types";
import {
  uploadVideos,
  startAnalysis,
  getStatus,
  getReport,
  getSidecar,
  getClipUrl,
  type SidecarResponse,
} from "@/lib/api";

/* ============================================================
   TYPES
   ============================================================ */
type Page = "upload" | "dashboard";

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
function LightboxModal({ clip, onClose }: { clip: ClipEntry; onClose: () => void }) {
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
function MustWatchClips({ clips }: { clips: ClipEntry[] }) {
  const [lightboxClip, setLightboxClip] = useState<ClipEntry | null>(null);

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
function downloadReportPDF(runId: string, date: string) {
  const a = document.createElement("a");
  a.href = `/api/report-pdf/${runId}`;
  a.download = `site_report_${date}.pdf`;
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

  // Real API state
  const [runId, setRunId] = useState<string | null>(null);
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const [parsedReport, setParsedReport] = useState<ParsedReport | null>(null);
  const [sidecar, setSidecar] = useState<SidecarResponse | null>(null);
  const [reportDate, setReportDate] = useState("");

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
    if (!parsedReport) return "SCREEN_CONTEXT: No report loaded";
    const video = parsedReport.videos[videoIndex];
    if (!video) return "SCREEN_CONTEXT: No video data";
    return [
      `SCREEN_CONTEXT:`,
      `Report: ${reportDate}, Video: ${video.filename}, Duration: ${video.duration}`,
      `Worker: Tony Stark, Site: #4`,
      `Scoreboard: Safety ${video.scores.safety}/100, Ergonomics ${video.scores.ergonomics}/100, Productivity ${video.scores.productivity}/100, Quality ${video.scores.quality}/100`,
      `Events Detected: ${video.eventsDetected}`,
      `Clips on screen:`,
      ...video.clips.map(c => `  - ${c.timestamp} | ${c.type} (${c.severity} severity) - Confidence: ${(c.confidence * 100).toFixed(0)}%`)
    ].join("\n");
  }, [parsedReport, reportDate]);

  /* ---------- Send context on dashboard entry or video change ---------- */
  useEffect(() => {
    if (page === "dashboard" && agentStatus === "connected") {
      const ctx = buildScreenContext(selectedVideoIndex);
      sendContextualUpdate(ctx);
    }
  }, [page, agentStatus, selectedVideoIndex, buildScreenContext, sendContextualUpdate]);


  /* ---------- Real Processing via API ---------- */
  const startProcessing = useCallback(async () => {
    if (uploadedFiles.length === 0) return;
    setProcessing(true);
    setProcessStep(0);
    addMsg("Uploading footage...", "jarvis");

    try {
      // 1. Upload
      const rid = await uploadVideos(uploadedFiles);
      setRunId(rid);
      setProcessStep(1);
      addMsg("Upload complete. Starting analysis...", "jarvis");

      // 2. Trigger analysis
      await startAnalysis(rid);
      setProcessStep(1);
      addMsg("Running spatial depth analysis...", "jarvis");

      // 3. Poll status
      const poll = () => new Promise<void>((resolve, reject) => {
        const interval = setInterval(async () => {
          try {
            const status = await getStatus(rid);
            // Map pipeline step to progress step index
            const stepMap: Record<string, number> = {
              "Starting pipeline": 1,
              "Scene selection": 1,
              "Sidecar construction": 1,
              "Activity labeling": 2,
              "Event extraction": 2,
              "Spatial query": 2,
              "Metrics computation": 2,
              "Report generation": 3,
              "Done": 4,
            };
            const stepIdx = stepMap[status.step] ?? processStep;
            setProcessStep(stepIdx);

            if (status.step === "Event extraction" || status.step === "Spatial query") {
              addMsg("Tracking hand and tool interactions...", "jarvis");
            } else if (status.step === "Report generation") {
              addMsg("Generating your performance report...", "jarvis");
            }

            if (status.status === "complete") {
              clearInterval(interval);
              resolve();
            } else if (status.status === "error") {
              clearInterval(interval);
              reject(new Error(status.error ?? "Pipeline error"));
            }
          } catch (err) {
            clearInterval(interval);
            reject(err);
          }
        }, 3000);
      });

      await poll();

      // 4. Fetch results
      setProcessStep(4);
      addMsg("Analysis complete. Loading results...", "jarvis");

      const [reportMd, sidecarData] = await Promise.all([
        getReport(rid),
        getSidecar(rid),
      ]);

      const parsed = parseReport(reportMd);
      setReportDate(parsed.date);

      // Rewrite clip paths to use API URLs
      for (const video of parsed.videos) {
        for (const clip of video.clips) {
          if (clip.clipPath && !clip.clipPath.startsWith("/api/")) {
            clip.clipPath = getClipUrl(rid, clip.clipPath);
          }
        }
      }

      setParsedReport(parsed);
      setSidecar(sidecarData);

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
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      addMsg(`Error: ${msg}`, "jarvis");
      setProcessing(false);
      setProcessStep(-1);
    }
  }, [uploadedFiles, addMsg, setTranscripts]);

  const switchVideo = (index: number) => {
    setSelectedVideoIndex(index);
    if (agentStatus !== "connected" && parsedReport) {
      addMsg(`Switching to ${parsedReport.videos[index]?.label ?? "video"}. Loading report data...`, "jarvis");
    }
  };

  const currentVideo = parsedReport?.videos[selectedVideoIndex];
  const scores = currentVideo?.scores;

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
          <p className="text-[0.65rem] text-[#6b7f99]">{reportDate || ""}</p>
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
            <div className="w-full flex flex-col items-center gap-4">
              <VideoUploadCard
                title="Upload Headcam Footage"
                description="Drop your video files here to begin AI-powered site analysis."
                className="w-full"
                onFilesSelected={(files) => setUploadedFiles(files)}
              />
              {uploadedFiles.length > 0 && (
                <button
                  className="mic-btn"
                  onClick={() => startProcessing()}
                >
                  Analyze {uploadedFiles.length} video{uploadedFiles.length > 1 ? "s" : ""}
                </button>
              )}
            </div>
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

  /* ---------- DASHBOARD PAGE ---------- */
  if (!parsedReport || !currentVideo || !scores) {
    return (
      <main className="h-screen flex items-center justify-center">
        <p className="text-[#6b7f99]">Loading report data...</p>
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
              {parsedReport.videos.map((v, i) => (
                <button
                  key={i}
                  className={`video-tab-item ${selectedVideoIndex === i ? "active" : ""}`}
                  onClick={() => switchVideo(i)}
                >
                  <span>{v.label}</span>
                  <span className="video-tab-duration">{v.duration}</span>
                  {selectedVideoIndex === i && <div className="video-tab-underline" />}
                </button>
              ))}
            </div>
            <div className="flex items-center pr-2 pb-1">
              <button className="ghost-btn" onClick={() => downloadReportPDF(runId ?? "", reportDate)}>
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
