"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { Upload, X, Play, Pause } from "lucide-react";

interface VideoUploadCardProps {
    className?: string;
    triggerAnimation?: boolean;
    onAnimationComplete?: () => void;
    onFileSelected?: (file: File) => void;
    title?: string;
    description?: string;
}

interface VideoComponentProps {
    isAnimating: boolean;
    onAnimationComplete?: () => void;
    filename?: string;
    onRemove?: () => void;
    videoUrl?: string;
}

interface UploadCardBaseProps {
    children?: React.ReactNode;
    className?: string;
    isDragOver?: boolean;
    isUploading?: boolean;
}

// Utility function to truncate filename
const truncateFilename = (filename: string, maxLength: number = 30) => {
    if (filename.length <= maxLength) return filename;
    const extension = filename.split(".").pop();
    const nameWithoutExt = filename.replace(`.${extension}`, "");
    const truncatedName = nameWithoutExt.substring(
        0,
        maxLength - 3 - extension!.length
    );
    return `${truncatedName}...${extension}`;
};

const VideoComponent = ({
    isAnimating,
    onAnimationComplete,
    filename = "video.mp4",
    onRemove,
    videoUrl,
}: VideoComponentProps) => {
    const [isRemoving, setIsRemoving] = useState(false);
    const [shouldShow, setShouldShow] = useState(false);
    const [isPlaying, setIsPlaying] = useState(false);
    const [videoLoaded, setVideoLoaded] = useState(false);
    const videoRef = useRef<HTMLVideoElement>(null);

    useEffect(() => {
        if (isAnimating) {
            setShouldShow(true);
        }
    }, [isAnimating]);

    useEffect(() => {
        if (videoUrl) {
            setVideoLoaded(false);
        }
    }, [videoUrl]);

    if (!shouldShow && !isRemoving) return null;

    const displayName = truncateFilename(filename);

    const handleRemove = () => {
        setIsRemoving(true);
        setIsPlaying(false);
    };

    const handleRemoveComplete = () => {
        setShouldShow(false);
        setIsRemoving(false);
        onRemove?.();
    };

    const handlePlayClick = () => {
        if (videoRef.current) {
            if (isPlaying) {
                videoRef.current.pause();
                setIsPlaying(false);
            } else {
                videoRef.current.play();
                setIsPlaying(true);
            }
        }
    };

    const handleVideoLoadedData = () => {
        setVideoLoaded(true);
        if (videoRef.current) {
            videoRef.current.addEventListener("ended", handleVideoEnd);
            videoRef.current.pause();
            videoRef.current.currentTime = 0.01;
        }
    };

    const handleVideoEnd = () => {
        setIsPlaying(false);
    };

    return (
        <AnimatePresence>
            {shouldShow && (
                <motion.div
                    className="absolute z-10"
                    initial={{
                        left: "50%",
                        top: "-300px",
                        x: "-50%",
                        y: 0,
                        opacity: 1,
                    }}
                    animate={
                        isRemoving
                            ? {
                                scale: 0,
                                opacity: 0,
                                filter: "blur(8px)",
                                transition: {
                                    duration: 0.4,
                                    ease: [0.23, 1, 0.32, 1],
                                },
                            }
                            : {
                                left: "50%",
                                top: "calc(50% - 0px)",
                                x: "-50%",
                                y: "-50%",
                                opacity: 1,
                                transition: {
                                    duration: 1.2,
                                    ease: [0.55, 0.055, 0.675, 0.19],
                                },
                            }
                    }
                    exit={{
                        scale: 0,
                        opacity: 0,
                        filter: "blur(8px)",
                        transition: {
                            duration: 0.4,
                            ease: [0.23, 1, 0.32, 1],
                        },
                    }}
                    style={{
                        transformOrigin: "center",
                    }}
                    onAnimationComplete={
                        isRemoving ? handleRemoveComplete : onAnimationComplete
                    }
                >
                    <motion.div
                        initial={{ scale: 0.9 }}
                        animate={
                            isRemoving
                                ? {
                                    scale: 0,
                                    transition: { duration: 0.4 },
                                }
                                : {
                                    scale: 1.0,
                                    transition: {
                                        type: "spring",
                                        stiffness: 250,
                                        damping: 15,
                                        mass: 1.2,
                                        delay: 0.7,
                                    },
                                }
                        }
                        className="rounded-lg bg-[#0d1520] backdrop-blur-sm shadow-lg relative group min-w-[400px] border border-[rgba(56,139,255,0.1)]"
                    >
                        {/* X button */}
                        <button
                            onClick={handleRemove}
                            className="absolute -top-2 -right-2 w-5 h-5 bg-red-500 text-white rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-200 hover:scale-110 z-30"
                        >
                            <X size={12} />
                        </button>

                        {/* Video Preview or Video Player */}
                        <div className="relative">
                            {videoUrl ? (
                                <div className="relative">
                                    <video
                                        ref={videoRef}
                                        src={videoUrl}
                                        className="w-full aspect-video object-cover rounded-md shadow-md border-t border-l border-r border-[rgba(56,139,255,0.1)]"
                                        onEnded={handleVideoEnd}
                                        onLoadedData={handleVideoLoadedData}
                                        controls={false}
                                        muted
                                        playsInline
                                    />
                                    {!videoLoaded && (
                                        <div className="absolute inset-0 bg-[#0d1520] rounded-md flex items-center justify-center">
                                            <div className="w-8 h-8 border-2 border-[#06b6d4] border-t-transparent rounded-full animate-spin"></div>
                                        </div>
                                    )}
                                    <button
                                        onClick={handlePlayClick}
                                        className="absolute bottom-0 left-0 w-8 h-8 rounded-full flex items-center justify-center transition-colors duration-200 group"
                                    >
                                        {isPlaying ? (
                                            <Pause size={14} className="text-white ml-0.5" />
                                        ) : (
                                            <Play size={14} className="text-white ml-0.5" />
                                        )}
                                    </button>
                                </div>
                            ) : (
                                <div className="w-full aspect-[21/9] bg-gradient-to-br from-[rgba(6,182,212,0.2)] to-[rgba(30,144,255,0.2)] rounded-md flex items-center justify-center cursor-pointer hover:from-[rgba(6,182,212,0.3)] hover:to-[rgba(30,144,255,0.3)] transition-colors duration-200">
                                    <div className="w-20 h-20 bg-[rgba(6,182,212,0.3)] rounded-full flex items-center justify-center hover:bg-[rgba(6,182,212,0.4)] transition-colors duration-200">
                                        <Play size={28} className="text-[#06b6d4] ml-1" />
                                    </div>
                                </div>
                            )}
                        </div>

                        <div className="mt-2 px-2 pb-2">
                            <span className="text-xs text-[#6b7f99] font-medium text-left block">
                                {displayName}
                            </span>
                        </div>
                    </motion.div>
                </motion.div>
            )}
        </AnimatePresence>
    );
};

const UploadCardBase = ({
    children,
    className,
    isDragOver = false,
    isUploading = false,
}: UploadCardBaseProps) => {
    const hasChildren = React.Children.count(children) > 0;

    return (
        <div className="relative">
            <div
                className={cn(
                    "rounded-xl min-h-[310px] flex items-center justify-center relative transition-colors duration-200 z-0",
                    !isUploading && "cursor-pointer hover:bg-[rgba(6,182,212,0.05)]",
                    isUploading
                        ? "bg-[rgba(6,182,212,0.1)]"
                        : isDragOver
                            ? "bg-[rgba(6,182,212,0.08)] shadow-inner"
                            : "bg-[rgba(10,15,25,0.5)]",
                    className
                )}
            >
                {!hasChildren && (
                    <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                        <Upload
                            size={48}
                            className={cn(
                                "transition-colors duration-200",
                                isDragOver ? "text-[#06b6d4]" : "text-[#6b7f99]",
                                isUploading && "text-[#06b6d4]"
                            )}
                        />
                    </div>
                )}

                <div className="relative z-10 w-full">{children}</div>
            </div>

            <div
                className={cn(
                    "absolute inset-0 rounded-xl border-2 border-dashed pointer-events-none z-20",
                    isUploading
                        ? "border-[rgba(6,182,212,0.4)]"
                        : isDragOver
                            ? "border-[rgba(6,182,212,0.6)]"
                            : "border-[rgba(56,139,255,0.15)]"
                )}
            />
        </div>
    );
};

export function VideoUploadCard({
    className,
    triggerAnimation = false,
    onAnimationComplete,
    onFileSelected,
    title = "Upload Your Video",
    description = "Drop in your videos and start playing instantly.",
}: VideoUploadCardProps) {
    const [isAnimating, setIsAnimating] = useState(false);
    const [isDragOver, setIsDragOver] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [uploadedFile, setUploadedFile] = useState<File | null>(null);
    const [videoUrl, setVideoUrl] = useState<string | null>(null);
    const fileInputRef = React.useRef<HTMLInputElement>(null);

    useEffect(() => {
        if (triggerAnimation) {
            setIsAnimating(true);
        }
    }, [triggerAnimation]);

    const handleAnimationComplete = () => {
        onAnimationComplete?.();
    };

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragOver(true);
    }, []);

    const handleDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragOver(false);
    }, []);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragOver(false);

        const files = Array.from(e.dataTransfer.files);
        const videoFile = files.find((file) => file.type.startsWith("video/"));

        if (videoFile) {
            setUploadedFile(videoFile);
            setIsUploading(true);

            const url = URL.createObjectURL(videoFile);
            setVideoUrl(url);

            onFileSelected?.(videoFile);

            setTimeout(() => {
                setIsUploading(false);
                setIsAnimating(true);
            }, 200);
        }
    }, []);

    const handleFileSelect = useCallback(
        (e: React.ChangeEvent<HTMLInputElement>) => {
            const file = e.target.files?.[0];
            if (file && file.type.startsWith("video/")) {
                setUploadedFile(file);
                setIsUploading(true);

                const url = URL.createObjectURL(file);
                setVideoUrl(url);

                onFileSelected?.(file);

                setTimeout(() => {
                    setIsUploading(false);
                    setIsAnimating(true);
                }, 200);
            }
        },
        []
    );

    const handleRemoveFile = useCallback(() => {
        setUploadedFile(null);
        setIsAnimating(false);
        if (videoUrl) {
            URL.revokeObjectURL(videoUrl);
            setVideoUrl(null);
        }
        if (fileInputRef.current) {
            fileInputRef.current.value = "";
        }
    }, [videoUrl]);

    const handleBaseClick = useCallback(() => {
        if (!isUploading && !uploadedFile) {
            fileInputRef.current?.click();
        }
    }, [isUploading, uploadedFile]);

    return (
        <motion.div
            className={cn("relative w-full max-w-lg mx-auto", className)}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
        >
            <div
                className={cn(
                    "relative overflow-hidden rounded-xl border border-[rgba(56,139,255,0.1)] bg-[rgba(10,15,25,0.6)] text-center"
                )}
            >
                <div
                    className="absolute top-0 left-0 right-0 bg-[rgba(10,15,25,0.6)] pointer-events-none z-30"
                    style={{
                        height: "24px",
                        borderRadius: "12px 12px 0 0",
                    }}
                />

                <div className="flex flex-col justify-center space-y-8 p-6">
                    <div className="relative w-full mx-auto">
                        <div
                            className="relative"
                            onDragOver={handleDragOver}
                            onDragLeave={handleDragLeave}
                            onDrop={handleDrop}
                            onClick={handleBaseClick}
                        >
                            <UploadCardBase
                                isDragOver={isDragOver}
                                isUploading={isUploading}
                            />

                            <VideoComponent
                                isAnimating={isAnimating}
                                onAnimationComplete={handleAnimationComplete}
                                filename={uploadedFile?.name}
                                onRemove={handleRemoveFile}
                                videoUrl={videoUrl || undefined}
                            />

                            <input
                                ref={fileInputRef}
                                type="file"
                                accept="video/*"
                                onChange={handleFileSelect}
                                className="sr-only"
                            />
                        </div>
                    </div>

                    <div className="flex flex-col items-start">
                        <h2 className="text-lg font-semibold text-[#c8d6e5] text-left">
                            {title}
                        </h2>
                        <p className="text-sm text-[#6b7f99] text-left">
                            {description}
                        </p>
                    </div>
                </div>
            </div>
        </motion.div>
    );
}
