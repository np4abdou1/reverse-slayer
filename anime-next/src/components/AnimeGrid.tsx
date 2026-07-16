import AnimeCard from './AnimeCard';

interface AnimeGridProps {
  animes: any[];
  limitRows?: number;
  maxCols?: 4 | 5 | 6;
}

export default function AnimeGrid({ animes, limitRows, maxCols = 4 }: AnimeGridProps) {
  if (!animes || animes.length === 0) {
    return (
      <div className="border border-border bg-card p-16 text-center text-muted-fg font-bold text-sm">
        لا توجد أنميات لعرضها حالياً.
      </div>
    );
  }

  let displayAnimes = animes;
  if (limitRows === 2) {
    displayAnimes = animes.slice(0, maxCols * 2);
  }

  const cols = maxCols === 4
    ? 'grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4 md:gap-5'
    : maxCols === 5
    ? 'grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4 md:gap-5'
    : 'grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4 md:gap-5';

  return (
    <div className={`grid ${cols}`}>
      {displayAnimes.map((anime: any, index: number) => (
        <AnimeCard key={`${anime.anime_id}-${index}`} anime={anime} />
      ))}
    </div>
  );
}
