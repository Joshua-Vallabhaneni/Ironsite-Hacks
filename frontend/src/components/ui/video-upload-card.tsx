"use client";

import React, { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Upload, X, Film } from "lucide-react";

interface VideoUploadCardProps {
    className?: string;
    onFilesSelected?: (files: File[]) => void;
    /** @deprecated use onFilesSelected */
    onFileSelected?: (file: File) => void;
    title?: string;
    description?: string;
}

export function VideoUploadCard({
    className,
    onFilesSelected,
    onFileSelected,
    title = "Upload Your Video",
    description = "Drop in your videos and start playing instantly.",
}: VideoUploadCardProps) {
    const [isDragOver, setIsDragOver] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [addedFiles, setAddedFiles] = useState<File[]>([]);
    const fileInputRef = React.useRef<HTMLInputElement>(null);

    // Fire parent callback whenever addedFiles changes — avoids setState-during-render
    useEffect(() => {
        onFilesSelected?.(addedFiles);
        if (!onFilesSelected && addedFiles[0]) onFileSelected?.(addedFiles[0]);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [addedFiles]);

    const acceptFiles = useCallback((files: File[]) => {
        const videoFiles = files.filter(
            f => f.type.startsWith("video/") || /\.(mp4|mov|avi|mkv|webm|hevc|mts|m2ts|h264)$/i.test(f.name)
        );
        if (!videoFiles.length) return;
        setIsUploading(true);
        setAddedFiles(prev => [...prev, ...videoFiles]);
        setTimeout(() => setIsUploading(false), 300);
    }, []);

    const removeFile = useCallback((index: number) => {
        setAddedFiles(prev => prev.filter((_, i) => i !== index));
    }, []);

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault(); e.stopPropagation(); setIsDragOver(true);
    }, []);

    const handleDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault(); e.stopPropagation(); setIsDragOver(false);
    }, []);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault(); e.stopPropagation(); setIsDragOver(false);
        acceptFiles(Array.from(e.dataTransfer.files));
    }, [acceptFiles]);

    const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files) acceptFiles(Array.from(e.target.files));
        e.target.value = "";
    }, [acceptFiles]);

    return (
        <motion.div
            className={cn("relative w-full max-w-lg mx-auto", className)}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
        >
            <div className="relative overflow-hidden rounded-xl border border-[rgba(56,139,255,0.1)] bg-[rgba(10,15,25,0.6)]">
                <div className="flex flex-col gap-5 p-6">
                    {/* Drop zone */}
                    <div
                        className={cn(
                            "rounded-xl min-h-[180px] flex flex-col items-center justify-center gap-3 border-2 border-dashed cursor-pointer transition-colors duration-200 p-6",
                            isDragOver
                                ? "border-[rgba(6,182,212,0.6)] bg-[rgba(6,182,212,0.08)]"
                                : "border-[rgba(56,139,255,0.2)] bg-[rgba(10,15,25,0.5)] hover:bg-[rgba(6,182,212,0.04)]"
                        )}
                        onDragOver={handleDragOver}
                        onDragLeave={handleDragLeave}
                        onDrop={handleDrop}
                        onClick={() => fileInputRef.current?.click()}
                    >
                        <Upload size={36} className={isDragOver ? "text-[#06b6d4]" : "text-[#6b7f99]"} />
                        <p className="text-[14px] text-[#6b7f99] text-center">
                            {isDragOver ? "Drop to add" : "Click or drag videos here — multiple supported"}
                        </p>
                        {isUploading && (
                            <p className="text-[12px] text-[#06b6d4] animate-pulse">Adding files...</p>
                        )}

                        {/* File chips */}
                        {addedFiles.length > 0 && (
                            <div
                                className="flex flex-wrap gap-2 mt-2 w-full justify-center"
                                onClick={e => e.stopPropagation()}
                            >
                                {addedFiles.map((f, i) => (
                                    <div
                                        key={i}
                                        className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[rgba(6,182,212,0.12)] border border-[rgba(6,182,212,0.25)] text-[#c8d6e5]"
                                    >
                                        <Film size={13} className="text-[#06b6d4] flex-shrink-0" />
                                        <span className="text-[12px] font-medium max-w-[200px] truncate">{f.name}</span>
                                        <button
                                            onClick={() => removeFile(i)}
                                            className="text-[#555] hover:text-[#ef4444] transition-colors flex-shrink-0"
                                        >
                                            <X size={12} />
                                        </button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                    <input
                        ref={fileInputRef}
                        type="file"
                        accept="video/*"
                        multiple
                        onChange={handleFileSelect}
                        className="sr-only"
                    />

                    <div className="flex flex-col items-start">
                        <h2 className="text-lg font-semibold text-[#c8d6e5]">{title}</h2>
                        <p className="text-sm text-[#6b7f99]">{description}</p>
                    </div>
                </div>
            </div>
        </motion.div>
    );
}
