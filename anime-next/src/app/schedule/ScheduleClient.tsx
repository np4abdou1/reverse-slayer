'use client';
import { useState, useMemo } from 'react';
import AnimeGrid from '@/components/AnimeGrid';
import { motion, AnimatePresence } from 'framer-motion';

const DAYS_ORDER = ['Saturday', 'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Unspecified'];
const DAY_NAMES: Record<string, string> = {
  'Saturday': 'السبت', 'Sunday': 'الأحد', 'Monday': 'الإثنين',
  'Tuesday': 'الثلاثاء', 'Wednesday': 'الأربعاء',
  'Thursday': 'الخميس', 'Friday': 'الجمعة',
  'Unspecified': 'غير محدد',
};

export default function ScheduleClient({ scheduleData, todayName }: { scheduleData: any; todayName: string }) {
  // Find first day that has entries, fallback to Saturday
  const defaultDay = useMemo(() => {
    if (scheduleData[todayName]?.length > 0) return todayName;
    return DAYS_ORDER.find(day => scheduleData[day]?.length > 0) || 'Saturday';
  }, [scheduleData, todayName]);

  const [activeDay, setActiveDay] = useState(defaultDay);

  const activeAnimes = (scheduleData[activeDay] || []).map((a: any) => {
    const { latest_episode_number, latest_episode_name, ...anime } = a;
    return anime;
  });

  return (
    <div className="flex flex-col gap-8 animate-fade-in">

      {/* Days Tabs */}
      <div className="flex flex-wrap gap-2 border-b border-border pb-6">
        {DAYS_ORDER.filter(day => scheduleData[day]?.length > 0).map((day) => {
          const isSelected = activeDay === day;
          const isToday = day === todayName;
          const count = scheduleData[day]?.length || 0;

          return (
            <button
              key={day}
              onClick={() => setActiveDay(day)}
              className="relative px-5 py-3 text-sm font-bold transition-all duration-200 cursor-pointer"
            >
              {isSelected && (
                <motion.div
                  layoutId="activeScheduleTab"
                  className="absolute inset-0 bg-foreground rounded-md shadow-md z-0"
                  transition={{ type: "spring", stiffness: 380, damping: 30 }}
                />
              )}
              <span className={`relative z-10 flex items-center gap-2 ${isSelected ? 'text-background font-black' : 'text-muted hover:text-foreground'}`}>
                {DAY_NAMES[day]}
                {isToday && (
                  <span className={`text-[9px] font-black uppercase px-1.5 py-0.5 rounded-sm ${isSelected ? 'bg-background/10 text-background' : 'bg-foreground/10 text-foreground'}`}>
                    اليوم
                  </span>
                )}
                <span className={`text-[10px] ${isSelected ? 'text-background/60' : 'text-muted/60'}`}>
                  ({count})
                </span>
              </span>
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      <div className="mt-4">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeDay}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
          >
            <AnimeGrid animes={activeAnimes} maxCols={5} />
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
