import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

type AudioController = {
  audio: HTMLMediaElement | null;
  currentMs: number;
  durationMs: number;
  isPlaying: boolean;
  playbackRate: number;
  volume: number;
  registerVideo: (video: HTMLVideoElement | null) => void;
  seek: (milliseconds: number) => void;
  toggle: () => Promise<void>;
  playRange: (startMs: number, endMs: number, loop?: boolean) => Promise<void>;
  setPlaybackRate: (rate: number) => void;
  setVolume: (volume: number) => void;
  skip: (milliseconds: number) => void;
};

const AudioContext = createContext<AudioController | null>(null);

export function AudioProvider({ source, children }: { source: string; children: React.ReactNode }) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const rangeRef = useRef<{ startMs: number; endMs: number; loop: boolean } | null>(null);
  const playbackRateRef = useRef(1);
  const volumeRef = useRef(1);
  const [videoElement, setVideoElement] = useState<HTMLVideoElement | null>(null);
  const [currentMs, setCurrentMs] = useState(0);
  const [durationMs, setDurationMs] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackRate, setRate] = useState(1);
  const [volume, setVolumeState] = useState(1);

  const getMedia = useCallback(() => videoRef.current ?? audioRef.current, []);
  const registerVideo = useCallback((video: HTMLVideoElement | null) => {
    if (!video && videoRef.current && audioRef.current) {
      audioRef.current.currentTime = videoRef.current.currentTime;
      audioRef.current.playbackRate = playbackRateRef.current;
      audioRef.current.volume = volumeRef.current;
    }
    videoRef.current = video;
    if (video) {
      const syncPosition = () => {
        if (audioRef.current && audioRef.current.currentTime > 0) {
          video.currentTime = audioRef.current.currentTime;
        }
        video.playbackRate = playbackRateRef.current;
        video.volume = volumeRef.current;
      };
      if (video.readyState >= 1) syncPosition();
      else video.addEventListener("loadedmetadata", syncPosition, { once: true });
    }
    setVideoElement(video);
  }, []);

  useEffect(() => {
    const media = videoElement ?? audioRef.current;
    if (!media) return;
    const update = () => {
      const current = Math.round(media.currentTime * 1000);
      const range = rangeRef.current;
      if (range && current >= range.endMs) {
        if (range.loop) {
          media.currentTime = range.startMs / 1000;
          void media.play();
        } else {
          media.pause();
          media.currentTime = range.endMs / 1000;
          rangeRef.current = null;
        }
      }
      setCurrentMs(Math.round(media.currentTime * 1000));
    };
    const metadata = () => setDurationMs(Math.round((media.duration || 0) * 1000));
    const play = () => setIsPlaying(true);
    const pause = () => setIsPlaying(false);
    media.addEventListener("timeupdate", update);
    media.addEventListener("loadedmetadata", metadata);
    media.addEventListener("play", play);
    media.addEventListener("pause", pause);
    return () => {
      media.removeEventListener("timeupdate", update);
      media.removeEventListener("loadedmetadata", metadata);
      media.removeEventListener("play", play);
      media.removeEventListener("pause", pause);
    };
  }, [source, videoElement]);

  const seek = useCallback((milliseconds: number) => {
    const media = getMedia();
    if (!media) return;
    rangeRef.current = null;
    const position = Math.max(0, milliseconds);
    media.currentTime = position / 1000;
    if (audioRef.current && media !== audioRef.current) audioRef.current.currentTime = position / 1000;
    setCurrentMs(position);
  }, [getMedia]);

  const toggle = useCallback(async () => {
    const media = getMedia();
    if (!media) return;
    rangeRef.current = null;
    if (media.paused) await media.play();
    else media.pause();
  }, [getMedia]);

  const playRange = useCallback(async (startMs: number, endMs: number, loop = false) => {
    const media = getMedia();
    if (!media) return;
    rangeRef.current = { startMs, endMs, loop };
    media.currentTime = startMs / 1000;
    if (audioRef.current && media !== audioRef.current) audioRef.current.currentTime = startMs / 1000;
    await media.play();
  }, [getMedia]);

  const setPlaybackRate = useCallback((rate: number) => {
    playbackRateRef.current = rate;
    const media = getMedia();
    if (media) media.playbackRate = rate;
    setRate(rate);
  }, [getMedia]);

  const setVolume = useCallback((next: number) => {
    const value = Math.max(0, Math.min(1, next));
    volumeRef.current = value;
    const media = getMedia();
    if (media) media.volume = value;
    setVolumeState(value);
  }, [getMedia]);

  const skip = useCallback((milliseconds: number) => {
    const media = getMedia();
    if (!media) return;
    media.currentTime = Math.max(0, Math.min(media.duration || Number.MAX_SAFE_INTEGER, media.currentTime + milliseconds / 1000));
  }, [getMedia]);

  const value = useMemo<AudioController>(() => ({
    audio: videoElement ?? audioRef.current,
    currentMs,
    durationMs,
    isPlaying,
    playbackRate,
    volume,
    registerVideo,
    seek,
    toggle,
    playRange,
    setPlaybackRate,
    setVolume,
    skip,
  }), [videoElement, currentMs, durationMs, isPlaying, playbackRate, volume, registerVideo, seek, toggle, playRange, setPlaybackRate, setVolume, skip]);

  return <AudioContext.Provider value={value}>
    <audio ref={audioRef} src={source} preload="metadata" aria-hidden="true" tabIndex={-1} style={{ display: "none" }} />
    {children}
  </AudioContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAudio(): AudioController {
  const value = useContext(AudioContext);
  if (!value) throw new Error("useAudio must be used inside AudioProvider");
  return value;
}
