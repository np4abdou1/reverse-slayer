import { getAnimeList } from '@/lib/anslayer';
import AnimeGrid from '@/components/AnimeGrid';
import EpisodeCard from '@/components/EpisodeCard';
import Link from 'next/link';

export const revalidate = 3600;

export default async function Home() {
  const [latestEpisodes, seasonPopular, topRated] = await Promise.all([
    getAnimeList('latest_updated_episode_new', 12, 0).catch(() => ({ data: [], total: 0 })),
    getAnimeList('top_currently_airing', 24, 0).catch(() => ({ data: [], total: 0 })),
    getAnimeList('top_anime_mal', 12, 0).catch(() => ({ data: [], total: 0 })),
  ]);

  return (
    <div className="flex flex-col gap-8 animate-fade-in">
      <section>
        <div className="flex items-end justify-between mb-8 pb-4 border-b border-border">
          <h2 className="text-2xl md:text-3xl font-black tracking-tight text-foreground flex items-center gap-3">
            <span className="w-1.5 h-8 bg-foreground"></span>
            أحدث الحلقات
          </h2>
          <Link
            href="/latest"
            className="text-xs font-bold text-muted hover:text-foreground border border-border hover:border-border-hover px-5 py-2.5 transition-all uppercase tracking-widest"
          >
            عرض الكل
          </Link>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {latestEpisodes.data.slice(0, 10).map((anime: any) => (
            <EpisodeCard key={anime.anime_id} anime={anime} />
          ))}
        </div>
      </section>

      <section>
        <div className="flex items-end justify-between mb-8 pb-4 border-b border-border">
          <h2 className="text-2xl md:text-3xl font-black tracking-tight text-foreground flex items-center gap-3">
            <span className="w-1.5 h-8 bg-muted"></span>
            الأكثر مشاهدة
          </h2>
          <Link
            href="/top/top_currently_airing"
            className="text-xs font-bold text-muted hover:text-foreground border border-border hover:border-border-hover px-5 py-2.5 transition-all uppercase tracking-widest"
          >
            عرض الكل
          </Link>
        </div>
        <AnimeGrid animes={seasonPopular.data} limitRows={2} maxCols={5} />
      </section>

      <section>
        <div className="flex items-end justify-between mb-8 pb-4 border-b border-border">
          <h2 className="text-2xl md:text-3xl font-black tracking-tight text-foreground flex items-center gap-3">
            <span className="w-1.5 h-8 bg-muted/60"></span>
            أعلى التقييمات
          </h2>
          <Link
            href="/top/top_anime_mal"
            className="text-xs font-bold text-muted hover:text-foreground border border-border hover:border-border-hover px-5 py-2.5 transition-all uppercase tracking-widest"
          >
            عرض الكل
          </Link>
        </div>
        <AnimeGrid animes={topRated.data} limitRows={2} maxCols={5} />
      </section>
    </div>
  );
}
