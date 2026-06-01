import { getEpisodeServers, getAnimeDetails } from "@/lib/anslayer";
import WatchClient from "./WatchClient";
import Link from "next/link";
import { ChevronLeft } from 'lucide-react';

export const dynamic = 'force-dynamic';

export default async function WatchPage({ 
  params, 
  searchParams 
}: { 
  params: Promise<{ id: string, episodeId: string }>,
  searchParams: Promise<{ name?: string }>
}) {
  const p = await params;
  const sp = await searchParams;
  const animeId = Number(p.id);
  const episodeId = Number(p.episodeId);
  const epName = sp.name || 'Episode';

  const [servers, anime] = await Promise.all([
    getEpisodeServers(animeId, episodeId),
    getAnimeDetails(animeId)
  ]);

  if (!servers || servers.length === 0) {
    return (
      <div className="container" style={{ padding: '80px 40px', textAlign: 'center' }}>
        <h1 style={{ color: 'var(--foreground)', fontSize: '1.3rem' }}>No servers found for this episode.</h1>
        <Link href={`/anime/${p.id}`} style={{ color: '#007aff', marginTop: '16px', display: 'inline-block', fontWeight: '600', fontSize: '14px' }}>Back to Anime</Link>
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      <div className="container" style={{ padding: '16px 24px 60px' }}>
        <Link href={`/anime/${p.id}`} style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-muted)', marginBottom: '16px', fontWeight: '700', fontSize: '12px' }}>
          <ChevronLeft size={14} />
          BACK TO ANIME
        </Link>

        <div style={{ marginBottom: '20px' }}>
          <h1 style={{ fontSize: '1.3rem', fontWeight: '800', color: '#000', marginBottom: '4px' }}>
            {anime?.anime_name}
          </h1>
          <h2 style={{ fontSize: '13px', color: 'var(--text-muted)', fontWeight: '600' }}>
            {epName}
          </h2>
        </div>

        <WatchClient servers={servers} />
      </div>
    </div>
  );
}
