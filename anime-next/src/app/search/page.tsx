import { searchAnime } from "@/lib/anslayer";
import AnimeCard from "@/components/AnimeCard";

export const dynamic = 'force-dynamic';

export default async function Search({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const sp = await searchParams;
  const query = sp.q || '';
  const animeList = query ? await searchAnime(query) : [];

  return (
    <div className="animate-fade-in">
      <div className="container" style={{ padding: '24px 24px 60px' }}>
        <h1 style={{ fontSize: '1.5rem', fontWeight: '800', marginBottom: '8px', color: '#000' }}>
          {query ? `Results for "${query}"` : 'Search Anime'}
        </h1>
        <p style={{ color: 'var(--text-muted)', marginBottom: '24px', fontWeight: '600', fontSize: '13px' }}>
          {animeList.length} results found.
        </p>
        <form action="/search" className="search-page-form">
          <input name="q" defaultValue={query} placeholder="Search by anime title" aria-label="Search by anime title" />
          <button type="submit">Search</button>
        </form>

        {animeList.length > 0 ? (
          <div className="anime-grid">
            {animeList.map((anime: any) => (
              <AnimeCard
                key={anime.anime_id}
                id={anime.anime_id}
                name={anime.anime_name}
                image={anime.anime_cover_image_url}
                rating={anime.anime_rating}
                type={anime.anime_type}
                year={anime.anime_release_year}
              />
            ))}
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '80px 0' }}>
            <h2 style={{ color: 'var(--text-muted)', fontWeight: '600', fontSize: '16px' }}>No results found. Try a different search.</h2>
          </div>
        )}
      </div>
    </div>
  );
}
