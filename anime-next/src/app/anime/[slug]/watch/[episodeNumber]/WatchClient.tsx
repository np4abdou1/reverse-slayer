'use client';
import { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import Link from 'next/link';
import Hls from 'hls.js';

interface ServerData {
  id: string;
  label: string;
  name: string;
  url: string;
  quality?: string;
}

function qScore(q: string | undefined): number {
  const order: Record<string, number> = { '2160p': 4, '1080p': 3, '720p': 2, '480p': 1, '360p': 0 };
  const key = (q || '').toLowerCase();
  for (const [k, v] of Object.entries(order)) {
    if (key.includes(k)) return v;
  }
  return -1;
}

function fmt(t: number): string {
  if (!isFinite(t) || t < 0) t = 0;
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const s = Math.floor(t % 60);
  const pad = (n: number) => String(n).padStart(2, '0');
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
}

export default function WatchClient({
  servers,
  animeSlug,
  title,
  epName,
}: {
  servers: ServerData[];
  animeId: string | number;
  animeSlug: string;
  title: string;
  epName: string;
}) {
  const sorted = useMemo(() => {
    const priority = (n: string): number => {
      const name = n.toLowerCase();
      if (name === 'anime3rb' || name.startsWith('anime3rb')) return 0;
      if (name === 'yonaplay') return 1;
      if (['google drive', 'mega', '4shared', 'mediafire', 'workupload', 'linkbox'].includes(name)) return 1;
      if (['streamwish', 'ok.ru', 'download'].includes(name)) return 2;
      if (name.includes('streamwish') || name.includes('swish') || name.includes('playerwish')) return 2;
      return 1;
    };
    return [...servers].sort((a, b) => {
      const ga = priority(a.name.toLowerCase());
      const gb = priority(b.name.toLowerCase());
      if (ga !== gb) return ga - gb;
      return a.name.localeCompare(b.name);
    });
  }, [servers]);

  const [activeIdx, setActiveIdx] = useState(0);
  const active = sorted[activeIdx] || null;
  const videoRef = useRef<HTMLVideoElement>(null);
  const hlsRef = useRef<Hls | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const hideTimer = useRef<NodeJS.Timeout | null>(null);
  const overlayTimer = useRef<NodeJS.Timeout | null>(null);
  const progressRef = useRef<HTMLDivElement>(null);

  const [playing, setPlaying] = useState(false);
  const [current, setCurrent] = useState(0);
  const [duration, setDuration] = useState(0);
  const [buffered, setBuffered] = useState(0);
  const [volume, setVolume] = useState(1);
  const [muted, setMuted] = useState(false);
  const [waiting, setWaiting] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showControls, setShowControls] = useState(true);
  const [isDragging, setIsDragging] = useState(false);
  const [dragTime, setDragTime] = useState<number | null>(null);
  const [showOverlay, setShowOverlay] = useState<'play' | 'pause' | null>(null);
  const [openServers, setOpenServers] = useState(false);

  const isIframe = active && !active.url.match(/\.(mp4|webm|m3u8)/i);

  const flashOverlay = useCallback((type: 'play' | 'pause') => {
    setShowOverlay(type);
    if (overlayTimer.current) clearTimeout(overlayTimer.current);
    overlayTimer.current = setTimeout(() => setShowOverlay(null), 400);
  }, []);

  // Init HLS
  useEffect(() => {
    const video = videoRef.current;
    if (!video || isIframe) return;
    if (hlsRef.current) { hlsRef.current.destroy(); hlsRef.current = null; }
    const url = active!.url;
    if (url.includes('.m3u8')) {
      if (Hls.isSupported()) {
        const hls = new Hls({ maxBufferLength: 30 });
        hlsRef.current = hls;
        hls.loadSource(url);
        hls.attachMedia(video);
        hls.on(Hls.Events.MANIFEST_PARSED, () => video.play().catch(() => {}));
      } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
        video.src = url;
      }
    } else {
      video.src = url;
    }
    video.currentTime = 5;
    video.play().catch(() => {});
    return () => { if (hlsRef.current) hlsRef.current.destroy(); };
  }, [active?.url]);

  // Video events
  useEffect(() => {
    const video = videoRef.current;
    if (!video || isIframe) return;
    const onTime = () => { if (!isDragging) setCurrent(video.currentTime); if (video.buffered.length) setBuffered(video.buffered.end(video.buffered.length - 1)); };
    const onMeta = () => setDuration(video.duration);
    const onPlay = () => { setPlaying(true); flashOverlay('play'); };
    const onPause = () => { setPlaying(false); flashOverlay('pause'); };
    const onWaiting = () => setWaiting(true);
    const onPlaying = () => setWaiting(false);
    const onVol = () => { setVolume(video.volume); setMuted(video.muted); };
    video.addEventListener('timeupdate', onTime);
    video.addEventListener('loadedmetadata', onMeta);
    video.addEventListener('play', onPlay);
    video.addEventListener('pause', onPause);
    video.addEventListener('waiting', onWaiting);
    video.addEventListener('playing', onPlaying);
    video.addEventListener('volumechange', onVol);
    video.addEventListener('durationchange', onMeta);
    return () => {
      video.removeEventListener('timeupdate', onTime);
      video.removeEventListener('loadedmetadata', onMeta);
      video.removeEventListener('play', onPlay);
      video.removeEventListener('pause', onPause);
      video.removeEventListener('waiting', onWaiting);
      video.removeEventListener('playing', onPlaying);
      video.removeEventListener('volumechange', onVol);
      video.removeEventListener('durationchange', onMeta);
    };
  }, [isIframe, isDragging]);

  // Fullscreen tracking
  useEffect(() => {
    const onFs = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', onFs);
    return () => document.removeEventListener('fullscreenchange', onFs);
  }, []);

  // Auto-hide controls
  const wake = useCallback(() => {
    setShowControls(true);
    if (hideTimer.current) clearTimeout(hideTimer.current);
    hideTimer.current = setTimeout(() => { if (playing && !isDragging && !openServers) setShowControls(false); }, 3000);
  }, [playing, isDragging, openServers]);

  useEffect(() => { wake(); return () => { if (hideTimer.current) clearTimeout(hideTimer.current); }; }, [wake]);

  // Seek drag
  const calcTimeFromX = useCallback((clientX: number) => {
    if (!progressRef.current || !duration) return 0;
    const rect = progressRef.current.getBoundingClientRect();
    return Math.max(0, Math.min(1, (clientX - rect.left) / rect.width)) * duration;
  }, [duration]);

  useEffect(() => {
    if (!isDragging) return;
    const onMove = (e: MouseEvent) => setDragTime(calcTimeFromX(e.clientX));
    const onUp = (e: MouseEvent) => { const t = calcTimeFromX(e.clientX); if (videoRef.current) videoRef.current.currentTime = t; setIsDragging(false); setDragTime(null); };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
  }, [isDragging, calcTimeFromX]);

  const togglePlay = useCallback(() => {
    const v = videoRef.current;
    if (!v) return;
    if (v.paused) { v.play(); flashOverlay('play'); } else { v.pause(); flashOverlay('pause'); }
  }, []);

  const skip = useCallback((delta: number) => {
    const v = videoRef.current;
    if (!v) return;
    v.currentTime = Math.max(0, Math.min(v.duration, v.currentTime + delta));
  }, []);

  const toggleMute = useCallback(() => {
    const v = videoRef.current;
    if (!v) return;
    v.muted = !v.muted;
  }, []);

  const toggleFullscreen = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    if (document.fullscreenElement) document.exitFullscreen();
    else el.requestFullscreen().catch(() => {});
  }, []);

  // Keyboard
  useEffect(() => {
    const video = videoRef.current;
    if (!video || isIframe) return;
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA') return;
      switch (e.key) {
        case ' ': case 'k': e.preventDefault(); togglePlay(); break;
        case 'j': e.preventDefault(); skip(-10); break;
        case 'l': e.preventDefault(); skip(10); break;
        case 'ArrowLeft': e.preventDefault(); skip(-5); break;
        case 'ArrowRight': e.preventDefault(); skip(5); break;
        case 'ArrowUp': e.preventDefault(); video.volume = Math.min(1, video.volume + 0.05); break;
        case 'ArrowDown': e.preventDefault(); video.volume = Math.max(0, video.volume - 0.05); break;
        case 'm': e.preventDefault(); toggleMute(); break;
        case 'f': e.preventDefault(); toggleFullscreen(); break;
        case 'Home': e.preventDefault(); video.currentTime = 0; break;
        case 'End': e.preventDefault(); video.currentTime = video.duration; break;
        default: if (e.key >= '0' && e.key <= '9') { e.preventDefault(); video.currentTime = (parseInt(e.key) / 10) * video.duration; }
      }
      wake();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isIframe, togglePlay, skip, toggleMute, toggleFullscreen, wake]);

  const pct = duration > 0 ? ((isDragging && dragTime !== null ? dragTime : current) / duration) * 100 : 0;
  const bufPct = duration > 0 ? (buffered / duration) * 100 : 0;
  const VolumeIcon = muted || volume === 0 ? 'mute' : volume < 0.5 ? 'low' : 'high';

  if (!active) {
    return (
      <div className="h-full flex items-center justify-center bg-black">
        <p className="text-white/50 text-lg">No servers available</p>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="fixed inset-0 w-screen h-screen bg-black text-white overflow-hidden select-none" dir="ltr" onMouseMove={wake} onTouchStart={wake}>
      <style>{`
        .ctrl-btn {
          display:flex;align-items:center;justify-content:center;
          width:2.5rem;height:2.5rem;border-radius:9999px;
          color:#fff;transition:background-color .18s ease,transform .18s ease;cursor:pointer;
        }
        .ctrl-btn:hover { background-color:rgba(255,255,255,.15); transform:scale(1.06); }
        .ctrl-btn:active { transform:scale(.94); }
        .mono-range { -webkit-appearance:none;appearance:none;height:4px;border-radius:9999px;background:rgba(255,255,255,.25);outline:none;cursor:pointer; }
        .mono-range::-webkit-slider-thumb { -webkit-appearance:none;width:13px;height:13px;border-radius:9999px;background:#fff;border:none;box-shadow:0 0 4px rgba(0,0,0,.6);cursor:pointer; }
        .mono-range::-moz-range-thumb { width:13px;height:13px;border-radius:9999px;background:#fff;border:none;cursor:pointer; }
        @keyframes scaleFade { 0%{opacity:1;transform:scale(1)} 100%{opacity:0;transform:scale(1.5)} }
        .animate-scale-fade{animation:scaleFade .5s ease-out forwards}
      `}</style>

      {/* Video */}
      {isIframe ? (
        <iframe src={active.url} className="w-full h-full border-0" allow="autoplay; fullscreen" allowFullScreen />
      ) : (
        <video ref={videoRef} className={`absolute inset-0 w-full h-full ${isFullscreen ? 'object-contain' : 'object-cover'} bg-black transition-[filter] duration-300 ${!playing ? 'grayscale' : 'grayscale-0'}`} playsInline onClick={togglePlay} onDoubleClick={toggleFullscreen} />
      )}

      {/* Loading spinner */}
      {!isIframe && waiting && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/60">
          <svg className="w-12 h-12 text-white animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12a9 9 0 1 1-6.219-8.56" /></svg>
        </div>
      )}

      {/* Play/pause overlay */}
      {!isIframe && (
        <div className={`absolute inset-0 pointer-events-none flex items-center justify-center z-10 ${showOverlay ? 'animate-scale-fade' : 'opacity-0'}`}>
          <div className="bg-black/50  p-5 flex items-center justify-center">
            {showOverlay === 'play' ? (
              <svg width="40" height="40" viewBox="0 0 24 24" fill="white"><path d="M8 5v14l11-7z"/></svg>
            ) : (
              <svg width="40" height="40" viewBox="0 0 24 24" fill="white"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
            )}
          </div>
        </div>
      )}

      {/* Persistent gradients (above logo, below controls) */}
      <div className={`absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-black/60 to-transparent pointer-events-none z-25 transition-opacity duration-200 ${showControls ? 'opacity-100' : 'opacity-0'}`} />
      <div className={`absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-black/70 to-transparent pointer-events-none z-25 transition-opacity duration-200 ${showControls ? 'opacity-100' : 'opacity-0'}`} />


      {/* Top bar */}
      {!isIframe && (
      <div className={`absolute top-0 inset-x-0 z-30 transition-opacity duration-200 ${showControls ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}>
        <div className="relative flex items-center justify-between px-6 pt-6">
          <Link href={`/anime/${animeSlug}`} className="flex-shrink-0 w-9 h-9 rounded-full bg-black/40 hover:bg-white/15 border border-white/10 flex items-center justify-center transition hover:scale-105">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 12H5"/><polyline points="12 19 5 12 12 5"/></svg>
          </Link>
          <div className="flex flex-col items-center justify-center flex-1 min-w-0 px-4">
            <h1 className="text-lg font-bold truncate text-white/90 drop-shadow-md">{title}</h1>
            <span className="text-xs text-white/60 drop-shadow-md mt-0.5">{epName}</span>
          </div>
          <div className="w-9" />
        </div>
      </div>
      )}

      {/* Bottom controls */}
      {!isIframe && (
      <div className={`absolute bottom-0 inset-x-0 z-30 transition-opacity duration-200 ${showControls ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}>
        <div className="relative px-6 pb-6">
          {/* Seek bar */}
          <div className="group/seek flex items-center gap-2 mb-3 pl-8 pr-4">
            <span className="text-[13px] font-mono text-white/80 tabular-nums w-12 text-right font-medium">{fmt(isDragging && dragTime !== null ? dragTime : current)}</span>
            <div ref={progressRef} className="relative flex-1 h-6 flex items-center cursor-pointer"
              onMouseDown={(e) => { setIsDragging(true); setDragTime(calcTimeFromX(e.clientX)); }}
            >
              <div className="absolute inset-x-0 h-1 group-hover/seek:h-1.5  bg-white/20 transition-all">
                <div className="absolute h-full  bg-white/30" style={{ width: `${bufPct}%` }} />
                <div className="absolute h-full  bg-white" style={{ width: `${pct}%` }} />
                <div className={`absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-3.5 h-3.5 rounded-full bg-white shadow-[0_0_8px_rgba(255,255,255,.8)] transition-all ${isDragging ? 'opacity-100 scale-125' : 'opacity-0 group-hover/seek:opacity-100'}`} style={{ left: `${pct}%` }} />
              </div>
            </div>
            <span className="text-[13px] font-mono text-white/80 tabular-nums w-12 font-medium">{fmt(duration)}</span>
          </div>

          {/* Buttons */}
          <div className="flex items-center gap-1 md:gap-2 pl-8 pr-4">
            <button onClick={togglePlay} className="ctrl-btn w-9 h-9">
              {playing ? (
                <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
              ) : (
                <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" className="translate-x-[1px]"><path d="M8 5v14l11-7z"/></svg>
              )}
            </button>


            {/* Volume */}
            <div className="group/vol flex items-center gap-0">
              <button onClick={toggleMute} className="ctrl-btn w-10 h-10 flex-shrink-0">
                {VolumeIcon === 'mute' ? (
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 5L6 9H2v6h4l5 4V5z"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/></svg>
                ) : (
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 5L6 9H2v6h4l5 4V5z"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>
                )}
              </button>
              <div className="w-0 group-hover/vol:w-20 overflow-hidden transition-all duration-200 flex items-center h-10">
                <input type="range" min={0} max={1} step={0.01} value={muted ? 0 : volume}
                  onChange={(e) => { const v = videoRef.current; if (!v) return; const val = parseFloat(e.target.value); v.volume = val; v.muted = val === 0; }}
                  className="mono-range w-20 align-middle" style={{ background: `linear-gradient(to right,white ${(muted ? 0 : volume) * 100}%,rgba(255,255,255,.25) ${(muted ? 0 : volume) * 100}%)` }}
                />
              </div>
            </div>

            <div className="flex-1" />

            {/* PiP */}
            <button onClick={async () => { const v = videoRef.current; if (!v) return; try { if (document.pictureInPictureElement) await document.exitPictureInPicture(); else await v.requestPictureInPicture(); } catch {} }} className="ctrl-btn w-10 h-10 hidden md:flex">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2"/><rect x="12" y="14" width="7" height="5" rx="1"/></svg>
            </button>

            <button onClick={toggleFullscreen} className="ctrl-btn w-10 h-10">
              {isFullscreen ? (
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3"/></svg>
              ) : (
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/></svg>
              )}
            </button>
          </div>
        </div>
      </div>
      )}

      {/* Server panel */}
      <div className="absolute right-0 top-1/2 -translate-y-1/2 z-50 flex items-start pointer-events-none">
        <div className={`pointer-events-auto transition-all duration-300 ease-out ${openServers ? 'max-w-[280px] opacity-100' : 'max-w-0 opacity-0'} overflow-hidden`}>
          <div className="bg-[#1a1a1a] border-y border-l border-[#333] py-3 min-w-[240px] max-h-[65vh] flex flex-col shadow-2xl">
            <div className="flex items-center gap-2 px-3 pb-3 border-b border-[#333] flex-shrink-0">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#aaa" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/></svg>
              <span className="text-[#aaa] text-sm font-semibold uppercase tracking-wider">Servers</span>
              <span className="ml-auto text-right text-[#666] text-[10px] truncate max-w-[100px]">{title}</span>
            </div>
            <div className="flex flex-col gap-0.5 overflow-y-auto flex-1 px-1.5 mt-1 scrollbar-thin">
              {sorted.map((srv, i) => {
                const isA3rb = srv.name === 'Anime3RB';
                const isActive = i === activeIdx;
                return (
                  <button key={`${srv.id}-${i}`} onClick={() => { setActiveIdx(i); setOpenServers(false); }}
                    className={`w-full text-left px-3 py-2 text-sm transition-all cursor-pointer flex items-center gap-3 ${
                      isActive
                        ? 'bg-white text-black font-semibold shadow-md'
                        : 'text-[#888] hover:text-white hover:bg-white/5'
                    }`}>
                    <span className={`w-6 h-6 flex items-center justify-center text-[10px] font-bold flex-shrink-0 ${
                      isA3rb
                        ? isActive ? 'bg-black/10 text-black' : 'bg-[#333] text-[#aaa]'
                        : isActive ? 'bg-black/10 text-black' : 'bg-[#2a2a2a] text-[#666]'
                    }`}>
                      {isA3rb ? srv.quality?.replace('p', '') || 'HD' : srv.quality?.replace('p', '') || 'W'}
                    </span>
                    <span className={`flex-1 truncate text-xs ${isActive ? 'font-bold' : 'font-medium'}`}>
                      {isA3rb ? `${srv.quality || 'HD'}` : `${srv.name}${srv.quality ? ` - ${srv.quality}` : ''}`}
                    </span>
                    {isActive && (
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="flex-shrink-0">
                        <polyline points="20 6 9 17 4 12"/>
                      </svg>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
        <button onClick={() => setOpenServers(!openServers)}
          className={`pointer-events-auto w-10 h-14 flex items-center justify-center cursor-pointer transition-all duration-300 border-y border-r shadow-lg ${
            openServers
              ? 'bg-[#1a1a1a] hover:bg-[#2a2a2a] border-[#333]'
              : 'bg-black/20 hover:bg-white/10 border-white/10'
          }`}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#aaa" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={`transition-transform duration-300 ${openServers ? 'rotate-180' : ''}`}><polyline points="9 18 15 12 9 6" /></svg>
        </button>
      </div>
    </div>
  );
}
