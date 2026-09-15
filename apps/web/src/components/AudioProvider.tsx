import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

type AudioController = {
  audio: HTMLAudioElement | null;
  currentMs: number;
  durationMs: number;
  isPlaying: boolean;
  playbackRate: number;
  volume: number;
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
  const rangeRef = useRef<{ startMs: number; endMs: number; loop: boolean } | null>(null);
  const [currentMs, setCurrentMs] = useState(0);
  const [durationMs, setDurationMs] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackRate, setRate] = useState(1);
  const [volume, setVolumeState] = useState(1);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const update = () => {
      const current = Math.round(audio.currentTime * 1000);
      const range = rangeRef.current;
      if (range && current >= range.endMs) {
        if (range.loop) {
          audio.currentTime = range.startMs / 1000;
          void audio.play();
        } else {
          audio.pause();
          audio.currentTime = range.endMs / 1000;
          rangeRef.current = null;
        }
      }
      setCurrentMs(Math.round(audio.currentTime * 1000));
    };
    const metadata = () => setDurationMs(Math.round((audio.duration || 0) * 1000));
    const play = () => setIsPlaying(true);
    const pause = () => setIsPlaying(false);
    audio.addEventListener("timeupdate", update);
    audio.addEventListener("loadedmetadata", metadata);
    audio.addEventListener("play", play);
    audio.addEventListener("pause", pause);
    return () => {
      audio.removeEventListener("timeupdate", update);
      audio.removeEventListener("loadedmetadata", metadata);
      audio.removeEventListener("play", play);
      audio.removeEventListener("pause", pause);
    };
  }, [source]);

  const seek = useCallback((milliseconds: number) => {
    const audio = audioRef.current;
    if (!audio) return;
    rangeRef.current = null;
    audio.currentTime = Math.max(0, milliseconds) / 1000;
    setCurrentMs(Math.max(0, milliseconds));
  }, []);

  const toggle = useCallback(async () => {
    const audio = audioRef.current;
    if (!audio) return;
    rangeRef.current = null;
    if (audio.paused) await audio.play();
    else audio.pause();
  }, []);

  const playRange = useCallback(async (startMs: number, endMs: number, loop = false) => {
    const audio = audioRef.current;
    if (!audio) return;
    rangeRef.current = { startMs, endMs, loop };
    audio.currentTime = startMs / 1000;
    await audio.play();
  }, []);

  const setPlaybackRate = useCallback((rate: number) => {
    const audio = audioRef.current;
    if (audio) audio.playbackRate = rate;
    setRate(rate);
  }, []);

  const setVolume = useCallback((next: number) => {
    const value = Math.max(0, Math.min(1, next));
    const audio = audioRef.current;
    if (audio) audio.volume = value;
    setVolumeState(value);
  }, []);

  const skip = useCallback((milliseconds: number) => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = Math.max(0, Math.min(audio.duration || Number.MAX_SAFE_INTEGER, audio.currentTime + milliseconds / 1000));
  }, []);

  const value = useMemo<AudioController>(() => ({
    audio: audioRef.current,
    currentMs,
    durationMs,
    isPlaying,
    playbackRate,
    volume,
    seek,
    toggle,
    playRange,
    setPlaybackRate,
    setVolume,
    skip,
  }), [currentMs, durationMs, isPlaying, playbackRate, volume, seek, toggle, playRange, setPlaybackRate, setVolume, skip]);

  return <AudioContext.Provider value={value}><audio ref={audioRef} src={source} preload="metadata" />{children}</AudioContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAudio(): AudioController {
  const value = useContext(AudioContext);
  if (!value) throw new Error("useAudio must be used inside AudioProvider");
  return value;
}
