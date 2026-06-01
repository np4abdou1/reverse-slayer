import { searchAnime } from "@/lib/anslayer";
import AnimeCard from "@/components/AnimeCard";
import Link from "next/link";

export const dynamic = 'force-dynamic';

export default async function Home({ searchParams }: { searchParams: Promise<{ type?: string, page?: string }> }) {
  const sp = await searchParams;
  const type = sp.type || 'latest_episodes';
  const currentPage = Number(sp.page) || 1;
  const offset = (currentPage - 1) * 24;
  
  const animeList = await searchAnime('', type, 24, offset);

  const categories = [
    { id: 'latest_episodes', name: 'Latest' },
    { id: 'currently_airing', name: 'Trending' },
    { id: 'top_anime', name: 'Top Rated' },
    { id: 'top_tv', name: 'TV Series' },
    { id: 'top_movie', name: 'Movies' },
  ];

  return (
    <div className="animate-fade-in">
      <div className="container" style={{ padding: '24px 24px 60px' }}>
        <section>
          <div style={{ marginBottom: '20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <h1 style={{ fontSize: '1.5rem', fontWeight: '800', color: '#000' }}>
              Browse
            </h1>
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              {categories.map((cat) => (
                <Link
                  key={cat.id}
                  href={`/?type=${cat.id}`}
                  style={{
                    padding: '6px 14px', borderRadius: '8px',
                    backgroundColor: type === cat.id ? '#000' : '#f5f5f7',
                    color: type === cat.id ? '#fff' : '#444',
                    fontSize: '12px', fontWeight: '700',
                    transition: 'all 0.2s', border: '1px solid var(--border)'
                  }}
                >
                  {cat.name}
                </Link>
              ))}
            </div>
          </div>

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

          <div className="pagination">
             {currentPage > 1 && (
               <Link href={`/?type=${type}&page=${currentPage - 1}`} className="page-btn">Previous</Link>
             )}
             <span className="page-btn active">{currentPage}</span>
             <Link href={`/?type=${type}&page=${currentPage + 1}`} className="page-btn">Next</Link>
          </div>
        </section>
      </div>
    </div>
  );
}
