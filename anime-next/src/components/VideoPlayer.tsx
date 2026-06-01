'use client';
import { useEffect, useRef, useState } from 'react';
import Hls from 'hls.js';
import { Maximize, Minimize, Play, Pause, Volume2, VolumeX } from 'lucide-react';

interface VideoPlayerProps {
  url: string;
  poster?: string;
}

export default function VideoPlayer({ url, poster }: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [progress, setProgress] = useState(0);
  const [duration, setDuration] = useState(0);
  const [showControls, setShowControls] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const controlsTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !url) return;

    setIsPlaying(false);
    setProgress(0);
    setDuration(0);

    let hls: Hls | null = null;
    const isM3U8 = url.includes('.m3u8');
    const isDirectVideo = /\.(mp4|webm)([\/?]|$)/i.test(url) || url.startsWith('/api/stream');

    if (isM3U8) {
      if (Hls.isSupported()) {
        hls = new Hls();
        hls.loadSource(url);
        hls.attachMedia(video);
      } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
        video.src = url;
      }
    } else if (isDirectVideo) {
      video.src = url;
    }

    return () => {
      if (hls) hls.destroy();
      video.pause();
      video.removeAttribute('src');
      video.load();
    };
  }, [url]);

  const togglePlay = () => {
    if (videoRef.current?.paused) {
      videoRef.current.play();
      setIsPlaying(true);
    } else {
      videoRef.current?.pause();
      setIsPlaying(false);
    }
  };

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      containerRef.current?.requestFullscreen();
    } else {
      document.exitFullscreen();
    }
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      switch (e.code) {
        case 'Space': e.preventDefault(); togglePlay(); break;
        case 'KeyF': toggleFullscreen(); break;
        case 'KeyM': setIsMuted(!isMuted); break;
        case 'ArrowLeft': if (videoRef.current) videoRef.current.currentTime -= 10; break;
        case 'ArrowRight': if (videoRef.current) videoRef.current.currentTime += 10; break;
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isMuted, isPlaying]);

  useEffect(() => {
    const onChange = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', onChange);
    return () => document.removeEventListener('fullscreenchange', onChange);
  }, []);

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setProgress((videoRef.current.currentTime / videoRef.current.duration) * 100);
    }
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration);
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (videoRef.current) {
      const time = (Number(e.target.value) / 100) * videoRef.current.duration;
      videoRef.current.currentTime = time;
      setProgress(Number(e.target.value));
    }
  };

  const formatTime = (seconds: number) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    return [h > 0 ? h : null, m, s].filter(x => x !== null).map(x => x!.toString().padStart(2, '0')).join(':');
  };

  const handleMouseMove = () => {
    setShowControls(true);
    if (controlsTimeoutRef.current) clearTimeout(controlsTimeoutRef.current);
    controlsTimeoutRef.current = setTimeout(() => setShowControls(false), 3000);
  };

  if (!url) {
    return (
      <div style={{
        aspectRatio: '16/9', backgroundColor: '#000', borderRadius: '12px',
        display: 'flex', alignItems: 'center', justifyContent: 'center'
      }}>
        <p style={{ color: '#666' }}>No streamable URL found for this server.</p>
      </div>
    );
  }

  const isM3U8 = url.includes('.m3u8');
  const isDirectVideo = /\.(mp4|webm)([\/?]|$)/i.test(url) || url.startsWith('/api/stream');
  const isMediafirePage = /(?:www\.)?mediafire\.com\/file/i.test(url);
  if (isMediafirePage) {
    return (
      <div style={{
        aspectRatio: '16/9', backgroundColor: '#000', borderRadius: '12px',
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center', gap: '16px', padding: '40px', textAlign: 'center'
      }}>
        <h3 style={{ color: '#fff', fontSize: '16px', fontWeight: '700' }}>Backup Server (MediaFire)</h3>
        <p style={{ color: '#999', fontSize: '13px' }}>The direct backup link could not be refreshed. Open the MediaFire page in a new tab.</p>
        <a href={url} target="_blank" rel="noopener noreferrer" style={{
          padding: '10px 20px', backgroundColor: '#fff', color: '#000',
          borderRadius: '8px', fontWeight: '700', fontSize: '13px'
        }}>
          Open MediaFire
        </a>
      </div>
    );
  }

  if (!isM3U8 && !isDirectVideo) {
    return (
      <div className="embed-container">
        <iframe
          key={url}
          src={url}
          allow="autoplay; fullscreen; picture-in-picture"
          allowFullScreen
          referrerPolicy="origin-when-cross-origin"
          title="Video player"
        />
        <a className="open-server-link" href={url} target="_blank" rel="noopener noreferrer">Open server</a>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      onMouseMove={handleMouseMove}
      style={{
        position: 'relative', width: '100%', aspectRatio: '16/9',
        backgroundColor: '#000', borderRadius: '12px', overflow: 'hidden',
        cursor: showControls ? 'default' : 'none'
      }}
    >
      <video
        ref={videoRef}
        poster={poster}
        muted={isMuted}
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onClick={togglePlay}
        style={{ width: '100%', height: '100%' }}
      />

      <div style={{
        position: 'absolute', inset: 0,
        background: 'linear-gradient(to top, rgba(0,0,0,0.7) 0%, transparent 20%, transparent 80%, rgba(0,0,0,0.7) 100%)',
        opacity: showControls ? 1 : 0, transition: 'opacity 0.3s',
        display: 'flex', flexDirection: 'column', justifyContent: 'space-between', padding: '16px'
      }}>
        <div style={{ display: 'flex', justifyContent: 'flex-end' }} />

        <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }}>
           <button onClick={togglePlay} style={{ background: 'rgba(255,255,255,0.1)', border: 'none', color: '#fff', borderRadius: '50%', width: '60px', height: '60px', display: 'flex', alignItems: 'center', justifyContent: 'center', backdropFilter: 'blur(10px)', cursor: 'pointer' }}>
             {isPlaying ? <Pause size={28} fill="currentColor" /> : <Play size={28} fill="currentColor" style={{ marginLeft: '4px' }} />}
           </button>
        </div>

        <div style={{ width: '100%' }}>
          <div style={{ position: 'relative', marginBottom: '10px' }}>
            <input
              type="range" min="0" max="100" value={progress}
              onChange={handleSeek}
              style={{
                width: '100%', cursor: 'pointer', accentColor: '#fff',
                height: '3px', appearance: 'none',
                backgroundColor: 'rgba(255,255,255,0.2)', borderRadius: '2px'
              }}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <button onClick={togglePlay} style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer', display: 'flex' }}>
                {isPlaying ? <Pause size={20} fill="currentColor" /> : <Play size={20} fill="currentColor" />}
              </button>
              <button onClick={() => setIsMuted(!isMuted)} style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer', display: 'flex' }}>
                {isMuted ? <VolumeX size={18} /> : <Volume2 size={18} />}
              </button>
              <span style={{ fontSize: '12px', fontWeight: '600', color: '#fff' }}>
                {formatTime(videoRef.current?.currentTime || 0)} / {formatTime(duration)}
              </span>
            </div>

            <button onClick={toggleFullscreen} style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer', display: 'flex' }}>
              {isFullscreen ? <Minimize size={18} /> : <Maximize size={18} />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
