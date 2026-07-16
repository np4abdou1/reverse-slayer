'use client';

import { useState, useEffect, useRef, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import AnimeGrid from '@/components/AnimeGrid';
import Pagination from '@/components/Pagination';
import { Snowflake, Leaf, Sun, Wind, Calendar, ArrowRight, ChevronDown } from 'lucide-react';
import Link from 'next/link';

const seasonAr: Record<string, string> = {
  'Winter': 'الشتاء',
  'Spring': 'الربيع',
  'Summer': 'الصيف',
  'Fall': 'الخريف',
};
const seasonOrder = ['Winter', 'Spring', 'Summer', 'Fall'];
const seasonIcon: Record<string, any> = {
  'Winter': Snowflake,
  'Spring': Leaf,
  'Summer': Sun,
  'Fall': Wind,
};

export default function SeasonsClient({
  year,
  season,
  sortedYears,
  total,
  animes,
  page,
  limit,
}: {
  year: string;
  season: string;
  sortedYears: string[];
  total: number;
  animes: any[];
  page: number;
  limit: number;
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [activeYear, setActiveYear] = useState(year);
  const [activeSeason, setActiveSeason] = useState(season);
  const [yearDropdownOpen, setYearDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const navigateTo = (newYear: string, newSeason: string) => {
    setActiveYear(newYear);
    setActiveSeason(newSeason);
    setYearDropdownOpen(false);
    startTransition(() => {
      router.push(`/seasons/${newYear}/${newSeason}`, { scroll: false });
    });
  };

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setYearDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const Icon = seasonIcon[activeSeason] || Calendar;
  const totalPages = Math.ceil(total / limit);

  return (
    <div className="animate-fade-in flex flex-col gap-8">
      {/* Top Filter Bar */}
      <div className="flex items-center justify-between flex-wrap gap-3 pb-6 border-b border-border" dir="rtl">

        {/* Left side: Breadcrumb + Year dropdown + Season tabs */}
        <div className="flex items-center gap-4 flex-wrap">
          {/* Breadcrumb */}
          <div className="flex items-center gap-1.5 text-xs text-muted font-bold">
            <Link href="/" className="hover:text-foreground transition-colors">الرئيسية</Link>
            <ArrowRight className="w-3 h-3 rotate-180" />
            <Link href="/seasons" className="hover:text-foreground transition-colors">المواسم</Link>
          </div>

          <span className="text-[#333] text-xs">|</span>

          {/* Year Dropdown */}
          <div className="relative" ref={dropdownRef}>
            <button
              onClick={() => setYearDropdownOpen(v => !v)}
              className="flex items-center gap-1.5 px-4 py-2 text-xs font-bold text-foreground bg-card border border-border hover:border-foreground transition-colors cursor-pointer rounded-lg shadow-sm"
            >
              <Calendar className="w-3.5 h-3.5" />
              <span>السنة: {activeYear}</span>
              <ChevronDown className={`w-3.5 h-3.5 transition-transform duration-300 ${yearDropdownOpen ? 'rotate-180' : ''}`} />
            </button>

            <AnimatePresence>
              {yearDropdownOpen && (
                <motion.div
                  initial={{ opacity: 0, y: -6, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -6, scale: 0.96 }}
                  transition={{ duration: 0.15 }}
                  className="absolute z-50 top-full right-0 mt-1.5 bg-card border border-border shadow-[0_20px_40px_rgba(0,0,0,0.5)] min-w-[140px] max-h-[260px] overflow-y-auto rounded-lg"
                >
                  <div className="flex flex-col py-1">
                    {sortedYears.map((y) => {
                      const isActive = y === activeYear;
                      return (
                        <button
                          key={y}
                          onClick={() => navigateTo(y, activeSeason)}
                          className={`text-right px-4 py-2 text-sm font-bold transition-colors ${
                            isActive
                              ? 'bg-foreground text-background'
                              : 'text-muted hover:bg-background hover:text-foreground'
                          }`}
                        >
                          {y}
                        </button>
                      );
                    })}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          <span className="text-[#333] text-xs">|</span>

          {/* Season Tabs (Rounded switches with slide animation) */}
          <div className="flex items-center gap-1 bg-card/60 p-1 rounded-xl border border-border">
            {seasonOrder.map((s) => {
              const I = seasonIcon[s];
              const isActive = s === activeSeason;
              return (
                <button
                  key={s}
                  onClick={() => navigateTo(activeYear, s)}
                  className="relative flex items-center gap-1.5 px-4 py-2 text-xs font-bold transition-all duration-200 cursor-pointer rounded-lg overflow-hidden"
                >
                  {isActive && (
                    <motion.div
                      layoutId="activeSeasonTab"
                      className="absolute inset-0 bg-foreground z-0 rounded-lg shadow-md"
                      transition={{ type: "spring", stiffness: 380, damping: 30 }}
                    />
                  )}
                  <span className={`relative z-10 flex items-center gap-1.5 transition-colors duration-200 ${isActive ? 'text-background font-black' : 'text-muted hover:text-foreground'}`}>
                    <I className="w-3.5 h-3.5" />
                    {seasonAr[s]}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Right side: Result count */}
        <div className="flex items-center gap-2 text-xs text-muted font-black bg-card/40 px-3 py-2 rounded-lg border border-border/50">
          <Icon className="w-4 h-4" strokeWidth={1.5} />
          <span>{total > 0 ? `${total} أنمي` : 'لا توجد أنميات'}</span>
        </div>
      </div>

      {/* Anime Grid Container with smooth loading state transition */}
      <div className="relative mt-4">
        {isPending && (
          <div className="absolute inset-0 bg-background/40 backdrop-blur-[1px] z-25 flex items-start justify-center pt-32 rounded-xl transition-all duration-300">
            <div className="flex flex-col items-center gap-4 bg-card/90 px-6 py-4 rounded-xl border border-border shadow-xl">
              <div className="w-6 h-6 border-2 border-foreground border-t-transparent rounded-full animate-spin" />
              <span className="text-xs font-black text-foreground">جاري تحميل الأنميات...</span>
            </div>
          </div>
        )}

        <AnimatePresence mode="wait">
          <motion.div
            key={`${activeYear}-${activeSeason}-${isPending}`}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.25 }}
            className={isPending ? 'opacity-30 pointer-events-none' : ''}
          >
            {total > 0 ? (
              <>
                <AnimeGrid animes={animes} maxCols={5} />
                {total > limit && (
                  <div className="mt-8 border-t border-border pt-8">
                    <Pagination
                      currentPage={page}
                      totalPages={totalPages}
                      hasNextPage={page < totalPages}
                      basePath={`/seasons/${activeYear}/${activeSeason}`}
                    />
                  </div>
                )}
              </>
            ) : (
              <div className="py-24 text-center flex flex-col items-center gap-3 border border-dashed border-border rounded-xl bg-card/10">
                <Calendar className="w-10 h-10 text-muted" />
                <p className="text-foreground font-bold">لا توجد أنميات لهذا الموسم بعد</p>
                <p className="text-sm text-muted">جرّب اختيار موسم آخر أو سنة أخرى من القائمة أعلاه.</p>
              </div>
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
