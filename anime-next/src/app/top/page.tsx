import { getAnimeList } from '@/lib/anslayer';
import AnimeGrid from '@/components/AnimeGrid';
import Link from 'next/link';

export const revalidate = 3600;

const SECTIONS = [
  {
    title: 'تقييم الموقع',
    subtitle: 'أفضل الأنميات حسب تقييم مستخدمي الموقع',
    items: [
      { label: 'أفضل الأنميات', type: 'top_anime', icon: '🏆', desc: 'جميع الأنميات مرتبة حسب التقييم' },
      { label: 'أفضل الأفلام', type: 'top_movie', icon: '🎬', desc: 'أفلام الأنمي الأعلى تقييماً' },
      { label: 'الأكثر مشاهدة', type: 'top_currently_airing', icon: '📺', desc: 'الأنميات الأكثر متابعة حالياً' },
      { label: 'أفضل المسلسلات', type: 'top_tv', icon: '📡', desc: 'المسلسلات التلفزيونية الأعلى تقييماً' },
      { label: 'الأكثر توقعاً', type: 'top_upcoming', icon: '🔥', desc: 'الأنميات القادمة الأكثر ترقباً' },
    ]
  },
  {
    title: 'تصنيف MyAnimeList',
    subtitle: 'التصنيف العالمي من MyAnimeList',
    items: [
      { label: 'أفضل الأنميات (MAL)', type: 'top_anime_mal', icon: '🌐', desc: 'التصنيف العالمي لـ MAL' },
      { label: 'أفضل الأفلام (MAL)', type: 'top_movie_mal', icon: '🎥', desc: 'أفلام الأنمي حسب MAL' },
      { label: 'الأكثر مشاهدة (MAL)', type: 'top_currently_airing_mal', icon: '📊', desc: 'الأكثر متابعة عالمياً' },
      { label: 'أفضل المسلسلات (MAL)', type: 'top_tv_mal', icon: '📺', desc: 'المسلسلات حسب MAL' },
    ]
  }
];

export default async function TopPage() {
  // Fetch first 6 from each top type for preview
  const previews = await Promise.all(
    ['top_anime', 'top_movie', 'top_currently_airing', 'top_tv', 'top_upcoming',
     'top_anime_mal', 'top_movie_mal', 'top_currently_airing_mal', 'top_tv_mal']
      .map(t => getAnimeList(t, 6, 0).catch(() => ({ data: [], total: 0 })))
  );

  const [topAnime, topMovie, topAiring, topTV, topUpcoming,
         topAnimeMal, topMovieMal, topAiringMal, topTVMal] = previews.map(r => r.data);

  const sectionData: Record<string, any[]> = {
    'top_anime': topAnime, 'top_movie': topMovie, 'top_currently_airing': topAiring,
    'top_tv': topTV, 'top_upcoming': topUpcoming,
    'top_anime_mal': topAnimeMal, 'top_movie_mal': topMovieMal,
    'top_currently_airing_mal': topAiringMal, 'top_tv_mal': topTVMal,
  };

  return (
    <div className="flex flex-col gap-8 animate-fade-in">
      {SECTIONS.map((group, gi) => (
        <section key={gi} className="flex flex-col gap-8">
          <div className="flex flex-wrap items-baseline gap-3 border-b border-border pb-2 mb-4" dir="rtl">
            <h2 className="text-xl md:text-2xl font-black tracking-tight text-foreground">{group.title}</h2>
            <span className="text-xs text-muted font-bold opacity-80">{group.subtitle}</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {group.items.map((item) => {
              const data = sectionData[item.type] || [];
              return (
                <Link
                  key={item.type}
                  href={`/top/${item.type}`}
                  className="border border-border bg-card p-5 hover:bg-card-hover transition-colors group flex flex-col gap-3"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-2xl">{item.icon}</span>
                    <div className="flex flex-col">
                      <span className="text-sm font-black text-foreground group-hover:text-foreground">{item.label}</span>
                      <span className="text-[11px] text-muted">{item.desc}</span>
                    </div>
                  </div>
                  {data.length > 0 && (
                    <div className="flex flex-col gap-1.5 border-t border-border pt-3 mt-1">
                      {data.slice(0, 3).map((a: any, i: number) => (
                        <div key={a.anime_id} className="flex items-center gap-2 text-xs">
                          <span className="w-5 h-5 bg-foreground/10 text-foreground flex items-center justify-center font-black text-[10px]">{(i + 1).toString().padStart(2, '0')}</span>
                          <span className="text-muted-fg truncate">{a.anime_english_title || a.anime_name}</span>
                           <span className="mr-auto text-[10px] text-muted font-bold">
                            {(() => {
                              const val = a.mal_score || a.anime_rating;
                              if (!val) return '';
                              const parsed = parseFloat(val);
                              return isNaN(parsed) ? '' : parsed.toFixed(2).replace(/\.?0+$/, '');
                            })()}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </Link>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
