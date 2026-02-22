"use client";

import { useConversation } from "@elevenlabs/react";
import { useState, useCallback, useRef, useEffect } from "react";

/* ============================================================
   TYPES
   ============================================================ */
export type JarvisState = "idle" | "speaking" | "listening";

export interface TranscriptMsg {
    id: number;
    text: string;
    sender: "jarvis" | "user";
}

const AGENT_ID = "agent_2501kj1sr2q5emr8bexc5zysemzg";

/* ============================================================
   HOOK: useJarvisAgent
   ============================================================ */
export function useJarvisAgent(autoStart = false) {
    const [transcripts, setTranscripts] = useState<TranscriptMsg[]>([]);
    const hasAutoStarted = useRef(false);
    const msgIdRef = useRef(2);

    const addMsg = useCallback((text: string, sender: "jarvis" | "user") => {
        setTranscripts((prev) => {
            const next = [...prev, { id: msgIdRef.current++, text, sender }];
            return next.slice(-8);
        });
    }, []);

    const conversation = useConversation({
        onConnect: () => {
            console.log("[JARVIS] Connected");
        },
        onDisconnect: () => {
            console.log("[JARVIS] Disconnected");
            addMsg("Session ended. Click Start Conversation to reconnect.", "jarvis");
        },
        onMessage: (message) => {
            console.log("[JARVIS] Message:", message);
            if (message.source === "ai") {
                addMsg(message.message, "jarvis");
            } else if (message.source === "user") {
                addMsg(message.message, "user");
            }
        },
        onError: (error) => {
            const errMsg = typeof error === "string" ? error : (error as any)?.message ?? "";
            if (errMsg.includes("shutdown") || errMsg.includes("AbortError")) {
                console.log("[JARVIS] Session closed (benign abort)");
                return;
            }
            console.error("[JARVIS] Error:", error);
            addMsg("I encountered an error. Please try reconnecting.", "jarvis");
        },
        onModeChange: (mode) => {
            console.log("[JARVIS] Mode changed:", mode);
        },
    });

    /* ---------- Derived State ---------- */
    const jarvisState: JarvisState =
        conversation.status !== "connected"
            ? "idle"
            : conversation.isSpeaking
                ? "speaking"
                : "listening";

    /* ---------- Session Controls ---------- */
    const startSession = useCallback(async () => {
        try {
            await navigator.mediaDevices.getUserMedia({ audio: true });
            await conversation.startSession({
                agentId: AGENT_ID,
                connectionType: "webrtc",
            });
        } catch (err) {
            console.error("[JARVIS] Failed to start session:", err);
            addMsg("Failed to start session. Please check your microphone permissions.", "jarvis");
        }
    }, [conversation, addMsg]);

    // Auto-start session on mount if requested
    useEffect(() => {
        if (autoStart && !hasAutoStarted.current) {
            hasAutoStarted.current = true;
            startSession();
        }
    }, [autoStart, startSession]);

    const endSession = useCallback(async () => {
        await conversation.endSession();
    }, [conversation]);

    /* ---------- Contextual Update (proper SDK method) ---------- */
    const sendContextualUpdate = useCallback(
        (text: string) => {
            if (conversation.status === "connected") {
                try {
                    conversation.sendContextualUpdate(text);
                    console.log("[JARVIS] Contextual update sent:", text.substring(0, 100) + "...");
                } catch (err) {
                    console.warn("[JARVIS] Failed to send contextual update:", err);
                }
            }
        },
        [conversation]
    );

    return {
        jarvisState,
        transcripts,
        setTranscripts,
        addMsg,
        status: conversation.status,
        isSpeaking: conversation.isSpeaking,
        startSession,
        endSession,
        sendContextualUpdate,
    };
}
