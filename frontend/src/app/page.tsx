"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  AlertTriangle,
  CheckCircle,
  Clock,
  Download,
  Folder,
  Mic,
  Play,
  Shield,
  Activity,
  Wrench,
  Award,
  TrendingUp,
  TrendingDown,
  BarChart3,
  HardHat,
  Eye,
} from "lucide-react";
import { VoicePoweredOrb } from "@/components/ui/voice-powered-orb";
import { GlowingEffect } from "@/components/ui/glowing-effect";
import { VideoUploadCard } from "@/components/ui/video-upload-card";

/* ============================================================
   TYPES
   ============================================================ */
type JarvisState = "idle" | "speaking" | "listening";
type Page = "upload" | "dashboard";
type Tab = "overview" | "safety" | "ergonomics" | "productivity" | "quality";

interface TranscriptMsg {
  id: number;
  text: string;
  sender: "jarvis" | "user";
}

/* ============================================================
   MOCK DATA — from the original dashboard
   ============================================================ */
const SCORES: Record<string, { score: number; delta: number; direction: "up" | "down" | "flat" }> = {
  safety: { score: 40, delta: -2, direction: "down" },
  ergonomics: { score: 95, delta: 3, direction: "up" },
  productivity: { score: 52, delta: 3, direction: "up" },
  quality: { score: 95, delta: 3, direction: "up" },
};

const KEY_FINDINGS = [
  {
    icon: "warning",
    title: "High severity PPE violation recorded due to a missing hard hat [00:06:04]",
    type: "alert",
  },
];

const CLIPS = [
  {
    time: "06:04 AM",
    tag: "Safety",
    tagColor: "bg-red-500 text-white",
    severity: "High",
    severityColor: "text-red-400",
    desc: "Missing hard hat violation",
    image: "/clips/ppe_1.jpg",
  },
  {
    time: "06:34 AM",
    tag: "Safety",
    tagColor: "bg-red-500 text-white",
    severity: "High",
    severityColor: "text-red-400",
    desc: "Missing hard hat violation",
    image: "/clips/ppe_2.jpg",
  },
  {
    time: "07:31 AM",
    tag: "Quality",
    tagColor: "bg-gray-800 text-gray-200",
    severity: "Medium",
    severityColor: "text-amber-400",
    desc: "Rework proxy detected",
    image: "/clips/rework.jpg",
  },
  {
    time: "02:01 AM",
    tag: "Productivity",
    tagColor: "bg-white text-black",
    severity: "Low",
    severityColor: "text-blue-500",
    desc: "Task transition",
    image: "/clips/transition.jpg",
  },
];

const SAFETY_DATA = {
  categories: [
    {
      name: "PPE Compliance",
      exposure: "0 min",
      count: 2,
      events: [
        { time: "06:04 AM", severity: "High", desc: "Missing hard hat [ppe_violation_6e3463]" },
        { time: "06:34 AM", severity: "High", desc: "Missing hard hat [ppe_violation_c4ae8a]" },
      ],
    },
    {
      name: "Falls",
      exposure: "0 min",
      count: 0,
      events: [],
    },
    {
      name: "Struck-By",
      exposure: "0 min",
      count: 0,
      events: [],
    },
    {
      name: "Caught-In/Between",
      exposure: "0 min",
      count: 0,
      events: [],
    },
  ],
};

const ERGO_DATA = {
  distribution: {
    low: { mins: 50 },
    medium: { mins: 5 },
    high: { mins: 1 },
  },
  recommendations: [
    { title: "Review Rework Proxy", desc: "A high-risk peak strain event occurred from 00:07:31 to 00:07:39." },
  ],
};

const PROD_DATA = {
  distribution: [
    { label: "Direct Work", mins: 2.8, pct: 5, color: "bg-[#10b981]" },
    { label: "Contributory", mins: 52.0, pct: 94, color: "bg-[#3b82f6]" },
    { label: "Non-contributory", mins: 0.8, pct: 1, color: "bg-[#ef4444]" },
  ],
  peakWindow: {
    timeRange: "Total Observed Time",
    duration: "55.6 min",
    efficiency: "Score: 51.7",
    desc: "A majority of time was spent in contributory activities instead of direct work.",
  },
  blockers: [
    {
      name: "Scaffolding",
      severity: "Low",
      duration: "1.0 min",
      occurrences: 1,
    },
    {
      name: "Repositioning",
      severity: "Low",
      duration: "1.0 min",
      occurrences: 1,
    },
    {
      name: "Brick Laying (Direct)",
      severity: "Low",
      duration: "0.5 min",
      occurrences: 1,
    },
  ],
};

const QUALITY_DATA = {
  checklists: [
    {
      title: "Work Periods",
      items: [
        { name: "No sustained work periods observed", status: "warn" },
      ]
    },
    {
      title: "Verification Moments",
      items: [
        { name: "00:00:58 - 00:01:03", status: "pass" },
      ]
    },
    {
      title: "Rework Signals",
      items: [
        { name: "00:07:31 - 00:07:39", status: "warn" },
      ]
    }
  ],
  reworkSignals: [
    { time: "07:31 AM", severity: "Medium", desc: "Rework proxy event detected" },
  ],
};

/* ============================================================
   COMPONENT: ScoreRing
   ============================================================ */
function ScoreRing({ score, size = 72 }: { score: number; size?: number }) {
  const r = (size - 6) / 2;
  const c = 2 * Math.PI * r;
  const offset = c - (score / 100) * c;

  return (
    <svg width={size} height={size} className="score-ring">
      <circle className="track" cx={size / 2} cy={size / 2} r={r} />
      <circle
        className="fill"
        cx={size / 2}
        cy={size / 2}
        r={r}
        style={{ strokeDashoffset: offset, strokeDasharray: c }}
      />
    </svg>
  );
}

/* ============================================================
   COMPONENT: FindingCard (Today's Headlines)
   ============================================================ */
function FindingCard({ finding }: { finding: typeof KEY_FINDINGS[0] }) {
  const IconComp =
    finding.type === "alert"
      ? AlertTriangle
      : finding.type === "success"
        ? CheckCircle
        : Clock;

  const colorClass =
    finding.type === "alert"
      ? "text-amber-400"
      : finding.type === "success"
        ? "text-cyan-400"
        : "text-blue-400";

  return (
    <div className="flex items-center gap-4 bg-[rgba(15,20,30,0.6)] border border-[rgba(255,255,255,0.05)] rounded-xl py-5 px-6 mb-4">
      <IconComp className={`h-6 w-6 flex-shrink-0 ${colorClass}`} />
      <h4 className="text-[17px] font-medium text-white tracking-wide">
        {finding.title}
      </h4>
    </div>
  );
}

/* ============================================================
   COMPONENT: ClipCard
   ============================================================ */
function ClipCard({ clip }: { clip: typeof CLIPS[0] }) {
  return (
    <div className="group flex flex-col rounded-xl overflow-hidden border border-[rgba(255,255,255,0.05)] bg-[rgba(15,20,30,0.6)]">
      {/* Image container */}
      <div className="relative h-[160px] w-full bg-black/50 overflow-hidden">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={clip.image} alt={clip.desc} className="object-cover w-full h-full opacity-80 group-hover:opacity-100 transition-opacity" />
        <div className="absolute top-2 right-2 bg-black/80 text-white text-[12px] font-medium font-mono px-2 py-1 rounded-md tracking-widest backdrop-blur-md">
          {clip.time}
        </div>
      </div>
      {/* Content */}
      <div className="p-4 flex flex-col flex-1">
        <div className="flex items-center gap-3 mb-3">
          <span className={`text-[12px] font-bold px-3 py-1 rounded-full ${clip.tagColor}`}>
            {clip.tag}
          </span>
          <span className={`text-[13px] font-medium ${clip.severityColor}`}>
            {clip.severity}
          </span>
        </div>
        <p className="text-[15px] text-white font-medium leading-snug">{clip.desc}</p>
      </div>
    </div>
  );
}

/* ============================================================
   TAB CONTENT COMPONENTS
   ============================================================ */
function OverviewTab() {
  return (
    <div className="space-y-[64px]">
      {/* Today's Headlines */}
      <section>
        <h3 className="text-xl font-bold text-white mb-6">Today's Headlines</h3>
        <div className="flex flex-col">
          {KEY_FINDINGS.map((f, i) => (
            <FindingCard key={i} finding={f} />
          ))}
        </div>
      </section>

      {/* Must-Watch Clips */}
      <section>
        <h3 className="text-xl font-bold text-white mb-6">Must-Watch Clips</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
          {CLIPS.map((c, i) => (
            <ClipCard key={i} clip={c} />
          ))}
        </div>
      </section>
    </div>
  );
}

function SafetyTab() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-8">
      {SAFETY_DATA.categories.map((cat, i) => {
        const hasEvents = cat.count > 0;
        return (
          <div key={i} className="bg-[rgba(15,20,30,0.6)] border border-[rgba(255,255,255,0.05)] rounded-2xl p-8 flex flex-col justify-between" style={{ minHeight: "280px" }}>
            <div className="flex justify-between items-start mb-6">
              <div className="flex gap-4 items-center">
                <div className={`p-3 rounded-xl flex items-center justify-center ${hasEvents ? "bg-amber-500/10 text-amber-500" : "bg-emerald-500/10 text-emerald-500"}`}>
                  {hasEvents ? <AlertTriangle className="h-6 w-6" /> : <HardHat className="h-6 w-6" />}
                </div>
                <div>
                  <h3 className="text-xl font-bold text-white">{cat.name}</h3>
                  <p className="text-sm text-gray-400 mt-1">Exposure: {cat.exposure}</p>
                </div>
              </div>
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center font-bold text-xl ${hasEvents ? "bg-[#ef4444] text-white" : "text-[rgba(255,255,255,0.1)] text-3xl"}`}>
                {cat.count}
              </div>
            </div>

            {hasEvents ? (
              <div className="mt-4 flex flex-col flex-1">
                <h4 className="text-[11px] font-bold text-gray-500 tracking-widest uppercase mb-3">Top Events</h4>
                <div className="space-y-3">
                  {cat.events.map((evt: any, j: number) => (
                    <div key={j} className="bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.05)] rounded-xl p-4">
                      <div className="flex items-center gap-4 mb-2">
                        <span className="text-sm text-blue-400 font-mono font-medium">{evt.time}</span>
                        <span className={`text-[11px] font-bold px-2 py-0.5 rounded-md ${evt.severity === "High" ? "bg-[#ef4444]/20 text-[#ef4444]" : "bg-amber-500/20 text-amber-500"}`}>
                          {evt.severity}
                        </span>
                      </div>
                      <p className="text-[15px] font-medium text-gray-200">{evt.desc}</p>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="mt-6 flex-1 flex flex-col justify-end pb-8">
                <div className="flex items-center gap-2 text-emerald-500 font-medium justify-center">
                  <CheckCircle className="h-5 w-5" /> No events detected
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function ErgonomicsTab() {
  const totalMins = ERGO_DATA.distribution.low.mins + ERGO_DATA.distribution.medium.mins + ERGO_DATA.distribution.high.mins;
  const radius = 90;
  const c = 2 * Math.PI * radius;

  const lowPct = ERGO_DATA.distribution.low.mins / totalMins;
  const medPct = ERGO_DATA.distribution.medium.mins / totalMins;

  const lowOffset = c - lowPct * c;
  const medOffset = c - medPct * c;
  const highOffset = c - (1 - lowPct - medPct) * c;

  // We rotate each segment so they stack nicely
  const lowAngle = -90;
  const medAngle = -90 + (lowPct * 360);
  const highAngle = medAngle + (medPct * 360);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* Posture Risk Distribution (Left) */}
      <div className="bg-[rgba(15,20,30,0.6)] border border-[rgba(255,255,255,0.05)] rounded-2xl p-8 flex flex-col">
        <h3 className="text-[22px] font-bold text-white tracking-wide mb-8">Posture Risk Distribution</h3>

        {/* Donut Chart */}
        <div className="relative w-[240px] h-[240px] mx-auto flex items-center justify-center flex-shrink-0">
          <svg width={240} height={240} className="relative z-10" style={{ transform: 'rotate(-90deg)' }}>
            {/* Low Risk (Green) */}
            <circle
              cx={120} cy={120} r={radius}
              fill="transparent"
              stroke="#10b981"
              strokeWidth={36}
              strokeDasharray={c}
              strokeDashoffset={lowOffset}
              style={{ transformOrigin: 'center', transform: `rotate(0deg)` }}
              className="transition-all duration-1000 ease-out"
            />
            {/* Medium Risk (Yellow) */}
            <circle
              cx={120} cy={120} r={radius}
              fill="transparent"
              stroke="#f59e0b"
              strokeWidth={36}
              strokeDasharray={c}
              strokeDashoffset={medOffset}
              style={{ transformOrigin: 'center', transform: `rotate(${lowPct * 360}deg)` }}
              className="transition-all duration-1000 ease-out"
            />
            {/* High Risk (Red) */}
            <circle
              cx={120} cy={120} r={radius}
              fill="transparent"
              stroke="#ef4444"
              strokeWidth={36}
              strokeDasharray={c}
              strokeDashoffset={highOffset}
              style={{ transformOrigin: 'center', transform: `rotate(${(lowPct + medPct) * 360}deg)` }}
              className="transition-all duration-1000 ease-out"
            />
            {/* Inner background to create donut gap effect */}
            <circle cx={120} cy={120} r={radius} fill="transparent" stroke="#0a0f19" strokeWidth={4} strokeDasharray="2 6" />
          </svg>
        </div>

        {/* Legend / Stats */}
        <div className="grid grid-cols-3 gap-4 mt-8 pt-6 border-t border-[rgba(255,255,255,0.05)] w-full text-center">
          <div>
            <div className="flex items-center justify-center gap-2 text-[14px] text-emerald-500 font-medium mb-2">
              <span className="w-3 h-3 bg-emerald-500 rounded-sm" /> Low Risk
            </div>
            <p className="text-3xl font-bold text-emerald-500">{ERGO_DATA.distribution.low.mins}</p>
            <p className="text-[12px] text-gray-500 mt-1">minutes</p>
          </div>
          <div>
            <div className="flex items-center justify-center gap-2 text-[14px] text-amber-500 font-medium mb-2">
              <span className="w-3 h-3 bg-amber-500 rounded-sm" /> Medium Risk
            </div>
            <p className="text-3xl font-bold text-amber-500">{ERGO_DATA.distribution.medium.mins}</p>
            <p className="text-[12px] text-gray-500 mt-1">minutes</p>
          </div>
          <div>
            <div className="flex items-center justify-center gap-2 text-[14px] text-[#ef4444] font-medium mb-2">
              <span className="w-3 h-3 bg-[#ef4444] rounded-sm" /> High Risk
            </div>
            <p className="text-3xl font-bold text-[#ef4444]">{ERGO_DATA.distribution.high.mins}</p>
            <p className="text-[12px] text-gray-500 mt-1">minutes</p>
          </div>
        </div>
      </div>

      {/* Recommended Interventions (Right) */}
      <div className="bg-[rgba(15,20,30,0.6)] border border-[rgba(255,255,255,0.05)] rounded-2xl p-8 flex flex-col">
        <h3 className="text-[22px] font-bold text-white tracking-wide mb-6">Recommended Interventions</h3>
        <div className="flex flex-col gap-5">
          {ERGO_DATA.recommendations.map((rec, i) => (
            <div key={i} className="flex gap-4 p-5 rounded-xl border border-blue-500/20 bg-blue-500/5 items-start">
              <div className="p-1 flex-shrink-0">
                <AlertTriangle className="h-5 w-5 text-blue-400" />
              </div>
              <div className="flex-1">
                <span className="text-[16px] text-white font-medium">{rec.title}</span>
                <span className="text-[16px] text-gray-300"> — {rec.desc}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ProductivityTab() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Time Distribution (Left) */}
        <div className="bg-[rgba(15,20,30,0.6)] border border-[rgba(255,255,255,0.05)] rounded-2xl p-8 flex flex-col">
          <h3 className="text-[22px] font-bold text-white tracking-wide mb-6">Time Distribution</h3>

          {/* Stacked Bar */}
          <div className="flex h-16 w-full rounded-xl overflow-hidden mb-8">
            {PROD_DATA.distribution.map((dist, i) => (
              <div
                key={i}
                className={`${dist.color} h-full flex items-center justify-center font-bold text-white text-[15px]`}
                style={{ width: `${dist.pct}%` }}
              >
                {dist.pct > 15 && `${dist.pct}%`}
              </div>
            ))}
          </div>

          {/* Legend */}
          <div className="flex flex-col gap-4 mt-auto">
            {PROD_DATA.distribution.map((dist, i) => (
              <div key={i} className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className={`w-4 h-4 rounded-md ${dist.color}`} />
                  <span className="text-[16px] text-gray-200">{dist.label}</span>
                </div>
                <div className="flex items-center gap-4 text-[15px]">
                  <span className="text-white font-bold">{dist.mins} min</span>
                  <span className="text-gray-500 font-mono w-8 text-right">{dist.pct}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Peak Performance Window (Right) */}
        <div className="bg-[#064e3b]/30 border border-[#059669]/30 rounded-2xl p-8 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 text-emerald-400 font-bold tracking-wide mb-4">
              <TrendingUp className="h-5 w-5" /> Peak Performance Window
            </div>
            <p className="text-sm text-gray-400 mb-1">Time Range</p>
            <p className="text-3xl font-bold text-white mb-6 tracking-wide">{PROD_DATA.peakWindow.timeRange}</p>

            <div className="grid grid-cols-2 gap-4 mb-8">
              <div>
                <p className="text-sm text-gray-400 mb-1">Duration</p>
                <p className="text-2xl font-bold text-emerald-400">{PROD_DATA.peakWindow.duration}</p>
              </div>
              <div>
                <p className="text-sm text-gray-400 mb-1">Efficiency</p>
                <p className="text-2xl font-bold text-emerald-400">{PROD_DATA.peakWindow.efficiency}</p>
              </div>
            </div>
          </div>

          <div className="bg-[#064e3b]/40 rounded-xl p-4 border border-[#059669]/20 flex gap-3 text-gray-200 text-sm leading-relaxed">
            <span className="text-emerald-400 font-bold w-4 h-4 flex-shrink-0 text-center">\ud83c\udfaf</span>
            <p>{PROD_DATA.peakWindow.desc}</p>
          </div>
        </div>
      </div>

      {/* Recurring Productivity Blockers */}
      <div className="bg-[rgba(15,20,30,0.6)] border border-[rgba(255,255,255,0.05)] rounded-2xl p-6">
        <h3 className="text-xl font-bold text-white tracking-wide mb-6">Recurring Productivity Blockers</h3>
        <div className="flex flex-col gap-4">
          {PROD_DATA.blockers.map((blocker, i) => (
            <div key={i} className="flex flex-col md:flex-row md:items-center justify-between p-5 rounded-xl bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.03)]">
              <div>
                <h4 className="text-[17px] font-bold text-white mb-2">{blocker.name}</h4>
                <div className="flex items-center gap-4 text-sm text-gray-400">
                  <span className="flex items-center gap-1.5"><Clock className="h-4 w-4" /> {blocker.duration}</span>
                  <span>{blocker.occurrences} occurrences</span>
                </div>
              </div>
              <span className="mt-4 md:mt-0 text-[12px] font-bold px-3 py-1 bg-[#ef4444] text-white rounded-md w-fit">
                {blocker.severity}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function QualityTab() {
  return (
    <div className="space-y-8 mb-8">
      {/* Checklists Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        {QUALITY_DATA.checklists.map((list, i) => (
          <div key={i} className="bg-[rgba(15,20,30,0.6)] border border-[rgba(255,255,255,0.05)] rounded-2xl p-6 flex flex-col">
            <h3 className="text-[0.7rem] uppercase tracking-widest text-[#6b7f99] font-medium mb-6">{list.title}</h3>
            <div className="flex flex-col divide-y divide-[rgba(255,255,255,0.05)] text-[13px]">
              {list.items.map((item, j) => (
                <div key={j} className="flex items-center justify-between py-4">
                  <span className="text-[#c8d6e5]">{item.name}</span>
                  {item.status === "pass" ? (
                    <div className="w-5 h-5 rounded-full border border-emerald-500/50 flex items-center justify-center">
                      <CheckCircle className="h-3.5 w-3.5 text-emerald-500" />
                    </div>
                  ) : (
                    <AlertTriangle className="h-5 w-5 text-amber-500" />
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Rework Signals */}
      <div className="bg-[rgba(15,20,30,0.6)] border border-[rgba(255,255,255,0.05)] rounded-2xl p-6">
        <h3 className="text-[0.7rem] uppercase tracking-widest text-[#6b7f99] font-medium mb-6">Rework Signals</h3>
        <div className="flex flex-col gap-4">
          {QUALITY_DATA.reworkSignals.map((sig, i) => (
            <div key={i} className="flex flex-col md:flex-row md:items-center justify-between p-5 rounded-xl border border-amber-500/20 bg-amber-500/5">
              <div>
                <span className="text-sm font-bold text-amber-500 font-mono tracking-widest">{sig.time}</span>
                <p className="text-[16px] text-gray-200 mt-2 font-medium leading-relaxed">{sig.desc}</p>
              </div>
              <span className={`mt-3 md:mt-0 text-[12px] font-bold px-3 py-1 rounded-md w-fit bg-white text-black`}>
                {sig.severity}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   MAIN PAGE
   ============================================================ */
export default function Home() {
  const [page, setPage] = useState<Page>("upload");
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [jarvisState, setJarvisState] = useState<JarvisState>("speaking");
  const [transcripts, setTranscripts] = useState<TranscriptMsg[]>([
    {
      id: 1,
      text: "Good morning. I'm JARVIS — your personal site intelligence system. Please upload today's headcam footage to begin analysis.",
      sender: "jarvis",
    },
  ]);
  const [holding, setHolding] = useState(false);
  const [dragover, setDragover] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [processStep, setProcessStep] = useState(-1);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const transcriptEndRef = useRef<HTMLDivElement>(null);
  const msgIdRef = useRef(2);

  // Auto-scroll transcripts
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcripts]);

  // Initial JARVIS idle after 4s
  useEffect(() => {
    const t = setTimeout(() => setJarvisState("idle"), 4000);
    return () => clearTimeout(t);
  }, []);

  const addMsg = useCallback((text: string, sender: "jarvis" | "user") => {
    setTranscripts((prev) => {
      const next = [...prev, { id: msgIdRef.current++, text, sender }];
      return next.slice(-6);
    });
  }, []);

  /* ---------- Processing Simulation ---------- */
  const startProcessing = useCallback(() => {
    setProcessing(true);
    setJarvisState("speaking");

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
        setJarvisState("speaking");
        setTranscripts([
          {
            id: msgIdRef.current++,
            text: "Analysis complete. Today's report is ready. I've identified 2 high-priority safety events and your worker achieved a productivity score of 74. Shall I walk you through the highlights?",
            sender: "jarvis",
          },
        ]);
        setTimeout(() => setJarvisState("idle"), 4000);
      }, 1200);
    }, cumulative);
  }, [addMsg]);

  const handleFileDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragover(false);
      if (e.dataTransfer.files.length > 0) startProcessing();
    },
    [startProcessing]
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files.length > 0) startProcessing();
    },
    [startProcessing]
  );

  /* ---------- Mic Hold ---------- */
  const handleMicDown = () => {
    setHolding(true);
    setJarvisState("listening");
  };

  const handleMicUp = () => {
    if (!holding) return;
    setHolding(false);
    addMsg("Can you tell me more about the safety events?", "user");
    setTimeout(() => {
      setJarvisState("speaking");
      addMsg(
        "Of course. Today I detected 2 near-miss events in the cutting zone. Both occurred when the blade guard wasn't properly positioned. I'd recommend a toolbox talk on guard protocols before tomorrow's shift.",
        "jarvis"
      );
      setTimeout(() => setJarvisState("idle"), 5000);
    }, 1000);
  };

  /* ---------- Tab Clicks with JARVIS response ---------- */
  const jarvisTabResponses: Record<Tab, string> = {
    overview: "Here's your daily overview. I'll highlight the most critical findings first.",
    safety: "Reviewing safety metrics. 2 near-miss events detected today — both in the cutting zone.",
    ergonomics: "Ergonomic analysis shows a posture score of 68. I've flagged 3 high-strain periods.",
    productivity: "Your productivity breakdown: 72% active work, 18% idle, 10% setup time.",
    quality: "Quality check: 3 verification moments passed, 1 minor rework signal detected.",
  };

  const switchTab = (tab: Tab) => {
    setActiveTab(tab);
    setJarvisState("speaking");
    addMsg(jarvisTabResponses[tab], "jarvis");
    setTimeout(() => setJarvisState("idle"), 3000);
  };

  /* ---------- JARVIS Panel (shared between upload & dashboard) ---------- */
  const JarvisPanel = () => (
    <div className="jarvis-panel w-full md:w-72 lg:w-80 flex flex-col items-center py-8 px-6 h-full relative z-10">
      {/* Title */}
      <h1 className="text-lg font-bold tracking-widest text-[#06b6d4] uppercase">
        JARVIS
      </h1>
      <p className="text-[0.6rem] text-[#6b7f99] tracking-[0.25em] uppercase mt-0.5">
        Personal AI Site Analysis
      </p>

      {/* Orb */}
      <div className="orb-glow w-44 h-44 my-6">
        <VoicePoweredOrb
          enableVoiceControl={false}
          hue={0}
          className="w-full h-full"
        />
      </div>

      {/* Waveform */}
      <div className={`waveform ${jarvisState === "speaking" ? "active" : jarvisState === "listening" ? "listening" : ""}`}>
        {Array.from({ length: 40 }).map((_, i) => {
          // Deterministic pseudo-random values based on index to avoid hydration mismatch
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

      {/* Status */}
      <div className="mt-3 text-[0.65rem] tracking-[0.2em] uppercase text-[#6b7f99] flex items-center gap-1">
        <span
          className={`pulse-dot ${jarvisState === "speaking" ? "speaking" : jarvisState === "listening" ? "listening" : "standby"}`}
        />
        {jarvisState === "speaking"
          ? "JARVIS IS SPEAKING..."
          : jarvisState === "listening"
            ? "LISTENING..."
            : "STANDBY"}
      </div>

      {/* Transcript */}
      <div className="w-full flex-1 mt-6 overflow-y-auto max-h-52 space-y-2">
        {transcripts.map((msg) => (
          <div key={msg.id} className={`transcript-bubble ${msg.sender}`}>
            {msg.text}
          </div>
        ))}
        <div ref={transcriptEndRef} />
      </div>

      {/* Mic Button (dashboard only) */}
      {page === "dashboard" && (
        <button
          className={`mic-btn mt-6 ${holding ? "active" : ""}`}
          onMouseDown={handleMicDown}
          onMouseUp={handleMicUp}
          onMouseLeave={() => holding && handleMicUp()}
        >
          <Mic className="h-4 w-4" />
          Hold to Speak
        </button>
      )}

      {/* Footer */}
      <div className="mt-auto pt-6 text-center">
        <p className="text-[0.65rem] text-[#6b7f99]">February 21, 2026</p>
        <p className="text-[0.7rem] text-[#c8d6e5] mt-1 flex items-center gap-1.5 justify-center">
          <span className="w-1.5 h-1.5 rounded-full bg-green-400" />
          Marcus Rivera · Site #4
        </p>
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
          {/* JARVIS Header — Centered */}
          <div className="flex flex-col items-center mb-10">
            <h1 className="text-lg font-bold tracking-widest text-[#06b6d4] uppercase">
              JARVIS
            </h1>
            <p className="text-[0.6rem] text-[#6b7f99] tracking-[0.25em] uppercase mt-0.5">
              Personal AI Site Analysis
            </p>

            {/* Orb */}
            <div className="orb-glow w-36 h-36 my-6">
              <VoicePoweredOrb
                enableVoiceControl={false}
                hue={0}
                className="w-full h-full"
              />
            </div>

            {/* Waveform */}
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

            {/* Status */}
            <div className="mt-3 text-[0.65rem] tracking-[0.2em] uppercase text-[#6b7f99] flex items-center gap-1">
              <span className={`pulse-dot ${jarvisState === "speaking" ? "speaking" : jarvisState === "listening" ? "listening" : "standby"}`} />
              {jarvisState === "speaking" ? "JARVIS IS SPEAKING..." : jarvisState === "listening" ? "LISTENING..." : "STANDBY"}
            </div>

            {/* Transcript */}
            <div className="w-full max-w-md mt-4 space-y-2">
              {transcripts.slice(-2).map((msg) => (
                <div key={msg.id} className={`transcript-bubble ${msg.sender}`}>
                  {msg.text}
                </div>
              ))}
            </div>
          </div>

          {/* Upload Card or Processing */}
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
                        className={`progress-step ${processStep === i ? "active" : processStep > i ? "done" : ""
                          }`}
                      >
                        <div className="step-dot">
                          {processStep > i ? "✓" : i + 1}
                        </div>
                      </div>
                      <span
                        className={`text-[0.7rem] mt-2 ${processStep >= i ? "text-[#c8d6e5]" : "text-[#6b7f99]"
                          }`}
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
  const TABS: { key: Tab; label: string }[] = [
    { key: "overview", label: "Overview" },
    { key: "safety", label: "Safety" },
    { key: "ergonomics", label: "Ergonomics" },
    { key: "productivity", label: "Productivity" },
    { key: "quality", label: "Quality" },
  ];

  return (
    <main className="h-screen flex relative overflow-hidden">
      <div className="bg-grid" />
      <div className="scanlines" />

      {/* Left: JARVIS Panel */}
      <aside className="hidden md:flex flex-col h-screen sticky top-0">
        <JarvisPanel />
      </aside>

      {/* Right: Report Content */}
      <div className="flex-1 relative z-10 overflow-y-auto h-screen">
        <div className="px-10 lg:px-16 py-12">
          {/* Header */}
          <div className="flex items-center justify-between mb-10">
            <div>
              <h2 className="text-xl font-light text-[#c8d6e5]">
                Daily Site Report
              </h2>
              <p className="text-sm text-[#6b7f99] mt-1">Marcus Rivera · Feb 21, 2026</p>
            </div>
            <button className="flex items-center gap-2 text-[0.75rem] text-[#6b7f99] hover:text-[#06b6d4] transition-colors border border-[rgba(56,139,255,0.1)] rounded-lg px-4 py-2.5 flex-shrink-0">
              <Download className="h-3.5 w-3.5" />
              Download PDF
            </button>
          </div>

          {/* Score Row */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-10">
            {(Object.entries(SCORES) as [string, typeof SCORES.safety][]).map(
              ([key, data]) => {
                const colorClass = key === "safety" ? "bg-amber-500" : key === "ergonomics" ? "bg-amber-400" : key === "productivity" ? "bg-yellow-500" : "bg-emerald-500";
                const textClass = key === "safety" ? "text-amber-500" : key === "ergonomics" ? "text-amber-400" : key === "productivity" ? "text-yellow-500" : "text-emerald-500";
                const borderClass = key === "safety" ? "border-amber-500/30" : key === "ergonomics" ? "border-amber-400/30" : key === "productivity" ? "border-yellow-500/30" : "border-emerald-500/30";

                return (
                  <div key={key} className={`bg-[rgba(15,20,30,0.6)] border ${borderClass} rounded-2xl p-6 relative flex flex-col justify-between overflow-hidden shadow-lg`}>
                    <div className="flex justify-between items-start mb-4">
                      <h3 className="text-[14px] font-medium text-gray-400 tracking-widest uppercase">{key}</h3>
                      <div className={`flex items-center gap-1 text-[13px] font-bold ${data.direction === "up" ? "text-emerald-500" : data.direction === "down" ? "text-[#ef4444]" : "text-gray-500"}`}>
                        {data.direction === "up" ? <TrendingUp className="h-4 w-4" /> : data.direction === "down" ? <TrendingDown className="h-4 w-4" /> : null}
                        {data.delta > 0 ? `+${data.delta}` : data.delta}
                      </div>
                    </div>

                    <div className="flex items-baseline gap-2 mb-8">
                      <span className={`text-[42px] leading-none font-bold ${textClass}`}>{data.score}</span>
                      <span className="text-[14px] font-medium text-gray-500">/100</span>
                    </div>

                    <div className="h-1.5 w-full bg-[rgba(255,255,255,0.05)] rounded-full overflow-hidden mt-auto">
                      <div className={`h-full ${colorClass}`} style={{ width: `${data.score}%` }} />
                    </div>
                  </div>
                );
              }
            )}
          </div>

          {/* Tab Bar */}
          <div className="flex gap-2 p-1 bg-[rgba(15,20,30,0.6)] border border-[rgba(255,255,255,0.05)] rounded-full w-fit mb-10 overflow-x-auto">
            {TABS.map((tab) => (
              <button
                key={tab.key}
                onClick={() => switchTab(tab.key)}
                className={`px-5 py-2 text-[14px] font-medium rounded-full transition-all whitespace-nowrap ${activeTab === tab.key
                  ? "bg-blue-600 text-white shadow-md shadow-blue-500/20"
                  : "text-gray-400 hover:text-gray-200 hover:bg-[rgba(255,255,255,0.05)]"
                  }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab Content */}
          <div className="pt-12 pb-16">
            {activeTab === "overview" && <OverviewTab />}
            {activeTab === "safety" && <SafetyTab />}
            {activeTab === "ergonomics" && <ErgonomicsTab />}
            {activeTab === "productivity" && <ProductivityTab />}
            {activeTab === "quality" && <QualityTab />}
          </div>
        </div>
      </div>
    </main>
  );
}
