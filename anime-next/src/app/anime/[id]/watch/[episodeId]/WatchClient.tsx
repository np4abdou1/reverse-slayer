'use client';
import { useState } from 'react';
import VideoPlayer from '@/components/VideoPlayer';

interface Server {
  id: string;
  label: string;
  name: string;
  url: string;
}

export default function WatchClient({ servers }: { servers: Server[] }) {
  const [activeIdx, setActiveIdx] = useState(0);

  if (!servers || servers.length === 0) {
    return <div className="error">No servers available for this episode.</div>;
  }

  const activeServer = servers[activeIdx] || servers[0];

  return (
    <div className="watch-layout">
      <div className="server-list">
        <div style={{
          fontSize: '10px', fontWeight: '700', color: 'var(--text-muted)',
          letterSpacing: '1px', marginBottom: '6px', textTransform: 'uppercase'
        }}>
          Servers ({servers.length})
        </div>
        {servers.map((srv, i) => (
          <button
            key={srv.id + i}
            onClick={() => setActiveIdx(i)}
            aria-pressed={i === activeIdx}
            style={{
              padding: '10px 14px', borderRadius: '2px',
              backgroundColor: i === activeIdx ? '#000' : 'transparent',
              color: i === activeIdx ? '#fff' : 'var(--text-muted)',
              border: i === activeIdx ? '1px solid #000' : '1px solid var(--border)',
              cursor: 'pointer', fontSize: '12px', fontWeight: '700',
              textAlign: 'left', transition: 'all 0.15s',
              display: 'flex', flexDirection: 'column', lineHeight: '1.3'
            }}
          >
            <span>{srv.name}</span>
            <span style={{ fontSize: '10px', opacity: 0.6, fontWeight: '500', marginTop: '2px' }}>{srv.label}</span>
          </button>
        ))}
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <VideoPlayer key={`${activeServer.id}-${activeIdx}-${activeServer.url}`} url={activeServer.url} />

        <div style={{
          marginTop: '16px', padding: '14px 18px',
          backgroundColor: '#f7f7f7', borderRadius: '2px',
          border: '1px solid var(--border)', color: '#666',
          fontSize: '12px', lineHeight: '1.5'
        }}>
          <strong style={{ color: '#000' }}>Note:</strong> If playback does not start, switch providers. MediaFire Backup links are refreshed when this page loads.
        </div>
      </div>
    </div>
  );
}
