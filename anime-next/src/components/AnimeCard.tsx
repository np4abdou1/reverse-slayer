import Link from 'next/link';
import { Star } from 'lucide-react';

interface AnimeCardProps {
  anime: any;
  isRelated?: boolean;
}

export default function AnimeCard({ anime, isRelated = false }: AnimeCardProps) {
  const slug = anime.anime_slug || anime.anime_id;
  const title = anime.anime_english_title || anime.anime_name || 'Unknown';
  const coverUrl = anime.mal_image || anime.anime_cover_image_full_url || anime.anime_cover_image_url;
  const ratingVal = anime.mal_score || (anime.anime_rating && anime.anime_rating !== '0.0' ? anime.anime_rating : null);
  const rating = (() => {
    if (!ratingVal) return null;
    const parsed = parseFloat(ratingVal);
    return isNaN(parsed) ? null : parsed.toFixed(2).replace(/\.?0+$/, '');
  })();
  const type = anime.anime_type || '';
  const status =
    anime.anime_status === 'Currently Airing'
      ? 'مستمر'
      : anime.anime_status === 'Finished Airing'
      ? 'مكتمل'
      : anime.anime_status === 'Not Yet Aired'
      ? 'قادم'
      : anime.anime_status || '';
  const episodeName = anime.latest_episode_name || '';
  const episodeNumber = anime.latest_episode_number || '';
  const year = anime.anime_release_year || '';
  const season = anime.anime_season || '';
  const ageRating = anime.anime_age_rating || '';
  const genres = anime.anime_genres ? (typeof anime.anime_genres === 'string' ? anime.anime_genres.split(/[،,]/).filter(Boolean) : anime.anime_genres) : [];
  const seasonAr: Record<string, string> = {
    'Winter': 'الشتاء', 'Spring': 'الربيع', 'Summer': 'الصيف', 'Fall': 'الخريف',
    'شتاء': 'الشتاء', 'ربيع': 'الربيع', 'صيف': 'الصيف', 'خريف': 'الخريف',
    'الخريف': 'الخريف', 'الشتاء': 'الشتاء', 'الربيع': 'الربيع', 'الصيف': 'الصيف'
  };
  
  let seasonDisplay = season || '';
  const seasonParts = seasonDisplay.split(' ');
  const seasonName = seasonParts[0];
  const translated = seasonAr[seasonName] || seasonName;
  if (seasonParts.length > 1) {
    seasonDisplay = `${translated} ${seasonParts.slice(1).join(' ')}`;
  } else {
    seasonDisplay = translated;
  }
  const showYear = year && !seasonDisplay.includes(String(year));
  const seasonYearDisplay = showYear ? `${seasonDisplay} ${year}` : seasonDisplay;
  const episodes = anime.anime_episode_count || '';

  const relationLabels: Record<string, string> = {
    'Sequel': 'تتمة',
    'Prequel': 'تمهيد',
    'Spin-off': 'فرعي',
    'Alternative Version': 'نسخة بديلة',
    'Alternative Setting': 'عالم بديل',
    'Parent Story': 'القصة الأصلية',
    'Full Story': 'القصة الكاملة',
    'Side Story': 'قصة جانبية',
    'Summary': 'ملخص',
    'Other': 'أخرى'
  };

  const linkHref = episodeNumber ? `/anime/${slug}/watch/${episodeNumber}` : `/anime/${slug}`;

  return (
    <Link
      href={linkHref}
      className="group relative block w-full bg-card border-2 border-border text-foreground transition duration-300 ease-out hover:-translate-y-1 hover:border-foreground hover:shadow-[0_0_50px_var(--glow)] [content-visibility:auto] [contain-intrinsic-size:420px]"
    >
      {/* Image Container */}
      <div className="relative aspect-[2/3] w-full overflow-hidden bg-background">
        {coverUrl ? (
          <img
            src={coverUrl}
            alt={title}
            className="absolute inset-0 w-full h-full object-cover transition-transform duration-400 ease-out group-hover:scale-105 will-change-transform"
            loading="lazy"
            width={400}
            height={600}
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center text-[#888] text-xs">لا توجد صورة</div>
        )}

        {/* Default Badges - hidden on hover */}
        <div className="absolute inset-0 pointer-events-none z-10 transition-opacity duration-300 ease-out group-hover:opacity-0">
          {isRelated && anime.relation_type ? (
            <div className="absolute top-2 right-2 bg-black/90 text-white px-2 py-0.5 text-[10px] font-black border border-[#444]">
              {relationLabels[anime.relation_type] || anime.relation_type}
            </div>
          ) : rating ? (
            <div className="absolute top-2 right-2 bg-black/80 text-white px-2 py-1 text-xs font-bold flex items-center gap-1 border border-[#333]">
              <Star className="w-3 h-3 fill-white" /> {rating}
            </div>
          ) : null}
          {type && (
            <div className="absolute top-2 left-2 bg-black/80 text-white px-2 py-1 text-xs font-bold uppercase border border-[#333]">{type}</div>
          )}
          {episodeName ? (
            <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/90 to-transparent pt-4 pb-1.5">
              <span className="text-xs font-bold text-white block text-center truncate px-2">{episodeName}</span>
            </div>
          ) : status ? (
            <div className="absolute bottom-2 left-2 bg-black/80 text-white/90 px-2 py-1 text-xs font-bold border border-[#333]">{status}</div>
          ) : null}
        </div>

        {/* HOVER OVERLAY - centered */}
        <div className="absolute inset-0 bg-black/60 p-4 flex items-center justify-center opacity-0 transition-opacity duration-300 ease-out group-hover:opacity-100">
          <div className="text-center w-full">

            {/* Staggered - Title */}
            <h3 className="font-black text-sm line-clamp-2 translate-y-2 opacity-0 transition-all duration-300 ease-out delay-0 group-hover:translate-y-0 group-hover:opacity-100 drop-shadow-lg text-white" dir="auto">
              {title}
            </h3>

          {/* Staggered - Meta Row (Rating, Type, Status) */}
          <div className="mt-1.5 flex items-center justify-center gap-3 text-xs text-white/90 translate-y-2 opacity-0 transition-all duration-300 ease-out delay-75 group-hover:translate-y-0 group-hover:opacity-100">
            {rating && <span className="font-bold text-white flex items-center gap-1 text-xs"><Star className="w-3 h-3 fill-white" /> {rating}</span>}
            {type && <span className="text-white/90">{type}</span>}
            {status && <span className="text-white/80">{status}</span>}
            {ageRating && <span className="text-white/70 border border-white/30 px-1.5 py-0.5 text-[10px]">{ageRating}</span>}
          </div>

            {/* Staggered - Season • Year • Episodes */}
            <div className="mt-1 text-xs text-white/70 text-center translate-y-2 opacity-0 transition-all duration-300 ease-out delay-100 group-hover:translate-y-0 group-hover:opacity-100" dir="rtl">
              {seasonYearDisplay && <span>{seasonYearDisplay} • </span>}
              {episodes && <span>{episodes} حلقة</span>}
            </div>

            {/* Staggered - Genres */}
            {genres.length > 0 && (
              <div className="mt-2 flex flex-wrap justify-center gap-x-2 gap-y-0.5 translate-y-2 opacity-0 transition-all duration-300 ease-out delay-100 group-hover:translate-y-0 group-hover:opacity-100 max-w-[200px] mx-auto text-[10px] text-white/80">
                {genres.map((g: string, i: number) => (
                  <span key={g} className="flex items-center gap-1.5">
                    {i > 0 && <span className="text-white/30">•</span>}
                    <span>{g.trim()}</span>
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Title Below Card */}
      <div className="p-3 bg-card transition-opacity duration-300 ease-out group-hover:opacity-30">
        <h3 className="font-black text-[13px] leading-tight line-clamp-1 text-center" title={title} dir="auto">{title}</h3>
      </div>
    </Link>
  );
}
