import { getAnimeDetails } from "@/lib/anslayer";
import Link from "next/link";
import { Play, Calendar, Star, Info, ChevronRight, ListVideo } from 'lucide-react';

export const dynamic = 'force-dynamic';

export default async function AnimeDetail({ params }: { params: Promise<{ id: string }> }) {
  const p = await params;
  const anime = await getAnimeDetails(Number(p.id));

  if (!anime || !anime.anime_id) {
    return (
      <div className="container" style={{ padding: '80px 0', textAlign: 'center' }}>
        <h1 style={{ color: 'var(--foreground)' }}>Anime Not Found</h1>
        <p style={{ color: 'var(--text-muted)', marginTop: '8px', fontSize: '14px' }}>The requested anime could not be retrieved.</p>
        <Link href="/" style={{ color: '#007aff', marginTop: '16px', display: 'inline-block', fontWeight: '600', fontSize: '14px' }}>Back to Home</Link>
      </div>
    );
  }

  const episodes = anime.episodes?.data || [];

  return (
    <div className="animate-fade-in">
      <div style={{
        position: 'relative', height: '280px', width: '100%', overflow: 'hidden', marginBottom: '-200px'
      }}>
        {anime.anime_cover_image_url && (
          <img
            src={anime.anime_cover_image_url}
            alt={anime.anime_name || 'Anime'}
            style={{ width: '100%', height: '100%', objectFit: 'cover', filter: 'blur(30px) brightness(0.9)', opacity: 0.25 }}
          />
        )}
        <div style={{
          position: 'absolute', bottom: 0, left: 0, right: 0, height: '100%',
          background: 'linear-gradient(to top, var(--background) 15%, transparent 100%)'
        }} />
      </div>

      <div className="container" style={{ position: 'relative', zIndex: 10 }}>
        <div style={{ display: 'flex', gap: '30px', flexWrap: 'wrap' }}>
          <div style={{ width: '200px', borderRadius: '14px', overflow: 'hidden', boxShadow: '0 10px 40px rgba(0,0,0,0.12)', border: '1px solid var(--border)', backgroundColor: '#fff', flexShrink: 0 }}>
            <img src={anime.anime_cover_image_url} alt={anime.anime_name || 'Anime'} style={{ width: '100%', display: 'block' }} />
          </div>

          <div style={{ flex: 1, minWidth: '280px', paddingTop: '20px' }}>
            <h1 style={{ fontSize: '2rem', fontWeight: '800', color: 'var(--foreground)', marginBottom: '12px', lineHeight: '1.1', letterSpacing: '-1px' }}>
              {anime.anime_name || 'Unknown Anime'}
            </h1>
            
            <div style={{ display: 'flex', gap: '16px', marginBottom: '16px', color: 'var(--text-muted)', fontWeight: '600', fontSize: '13px', flexWrap: 'wrap' }}>
              {anime.anime_rating && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Star size={14} fill="#000" color="#000" />
                  <span style={{ color: '#000', fontWeight: '700' }}>{anime.anime_rating}</span>
                </div>
              )}
              {anime.anime_release_year && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Calendar size={14} />
                  <span>{anime.anime_release_year}</span>
                </div>
              )}
              {anime.anime_type && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Info size={14} />
                  <span>{anime.anime_type}</span>
                </div>
              )}
              {anime.anime_status && (
                <div style={{ border: '1px solid var(--border)', padding: '2px 8px', borderRadius: '5px', fontSize: '11px' }}>
                  {anime.anime_status}
                </div>
              )}
            </div>

            <p style={{ fontSize: '14px', color: 'var(--foreground)', lineHeight: '1.6', marginBottom: '20px', maxWidth: '700px', fontWeight: '400', opacity: 0.75 }}>
              {anime.anime_description || 'No description available.'}
            </p>

            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              {(anime.anime_genres || '').split(',').map((g: string) => g.trim() ? (
                <span key={g} style={{
                  padding: '5px 14px', backgroundColor: '#f5f5f7',
                  border: '1px solid var(--border)', borderRadius: '8px',
                  fontSize: '12px', fontWeight: '600', color: '#444'
                }}>
                  {g.trim()}
                </span>
              ) : null)}
            </div>
          </div>
        </div>

        <section className="episodes-section">
          <div className="episodes-heading">
            <div className="episodes-title">
              <div className="episodes-title-icon"><ListVideo size={18} /></div>
              <div>
                <h2>Episodes</h2>
                <p>Select an episode to start watching</p>
              </div>
            </div>
            <span className="episodes-count">{episodes.length} episodes</span>
          </div>

          <div className="episode-list">
            {episodes.map((ep: any, index: number) => (
              <Link
                key={ep.episode_id}
                href={`/anime/${p.id}/watch/${ep.episode_id}?name=${encodeURIComponent(ep.episode_name)}`}
                className="episode-card"
              >
                <div className="episode-number">
                  {String(ep.episode_number || index + 1).padStart(2, '0')}
                </div>
                <div className="episode-card-copy">
                  <span>{ep.episode_name}</span>
                  <small>Episode {ep.episode_number || index + 1}</small>
                </div>
                <div className="episode-play"><Play size={13} fill="currentColor" /></div>
                <ChevronRight className="episode-arrow" size={17} />
              </Link>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
