import { searchAnime } from '@/lib/anslayer';
import AnimeGrid from '@/components/AnimeGrid';
import Pagination from '@/components/Pagination';

export default async function SearchPage({ searchParams }: { searchParams: Promise<{ [key: string]: string | undefined }> }) {
  const sp = await searchParams;
  const page = Number(sp.page) || 1;
  const limit = 48;
  const offset = (page - 1) * limit;

  const query = sp.q || '';
  const { data: results, total } = query ? await searchAnime(query, limit, offset).catch(() => ({ data: [], total: 0 })) : { data: [], total: 0 };
  const totalPages = Math.ceil(total / limit);

  if (!query) {
    return (
      <div className="flex flex-col items-center justify-center py-32 text-center gap-4 animate-fade-in">
        <p className="text-muted font-bold text-sm">استخدم زر البحث في الأعلى للبحث عن أنمي</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8 animate-fade-in">
      <div className="flex items-center justify-between border-b border-border pb-4">
        <p className="text-sm text-muted">
          نتائج البحث عن: <span className="text-foreground font-bold">&quot;{query}&quot;</span>
        </p>
        <span className="text-xs text-muted font-bold">{total} نتيجة</span>
      </div>
      {results.length > 0 ? (
        <>
          <AnimeGrid animes={results} />
          <Pagination
            currentPage={page}
            totalPages={totalPages}
            hasNextPage={page < totalPages}
            basePath="/search"
            queryString={`&q=${query}`}
          />
        </>
      ) : (
        <div className="border border-border bg-card p-16 text-center text-muted font-bold text-base">
          لا توجد نتائج مطابقة لـ &quot;{query}&quot;
        </div>
      )}
    </div>
  );
}
