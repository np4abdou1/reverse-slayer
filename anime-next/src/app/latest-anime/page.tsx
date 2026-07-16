import { getAnimeList } from '@/lib/anslayer';
import AnimeGrid from '@/components/AnimeGrid';
import Pagination from '@/components/Pagination';

export const revalidate = 3600;

export default async function LatestAnimeAdded({ searchParams }: { searchParams: Promise<{ page?: string }> }) {
  const sp = await searchParams;
  const page = Number(sp.page) || 1;
  const limit = 48;
  const offset = (page - 1) * limit;
  const { data: latestAnime, total } = await getAnimeList('last_added_tv', limit, offset).catch(() => ({ data: [], total: 0 }));
  const totalPages = Math.ceil(total / limit);

  return (
    <div className="flex flex-col">
      <div className="flex flex-wrap items-baseline justify-between border-b border-border pb-3 mb-5" dir="rtl">
        <h1 className="text-xl md:text-2xl font-black tracking-tight text-foreground">اخر الانميات المضافة</h1>
        <span className="text-xs text-muted font-bold opacity-80">صفحة {page} من {totalPages || 1}</span>
      </div>
      <AnimeGrid animes={latestAnime} maxCols={5} />
      <Pagination currentPage={page} totalPages={totalPages} hasNextPage={page < totalPages} basePath="/latest-anime" />
    </div>
  );
}
