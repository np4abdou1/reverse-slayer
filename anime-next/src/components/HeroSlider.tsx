'use client';
import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { Play, Info } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export default function HeroSlider({ animes }: { animes: any[] }) {
  const [current, setCurrent] = useState(0);
  const [isPaused, setIsPaused] = useState(false);

  const slides = animes
    .filter(a => a.anime_banner_image_url || a.anime_anilist_banner)
    .slice(0, 5)
    .map(a => ({
      id: a.anime_id,
      slug: a.anime_slug || a.anime_id,
      title: a.anime_english_title || a.anime_name || 'Unknown',
      desc: a.anime_description || '',
      bannerUrl: a.anime_anilist_banner || a.anime_banner_image_url,
      rating: (() => {
        const val = a.mal_score || a.anime_rating;
        if (!val) return '--';
        const parsed = parseFloat(val);
        return isNaN(parsed) ? '--' : parsed.toFixed(2).replace(/\.?0+$/, '');
      })(),
      type: a.anime_type || '',
    }));

  useEffect(() => {
    if (isPaused || slides.length <= 1) return;
    const timer = setInterval(() => setCurrent(p => (p + 1) % slides.length), 7000);
    return () => clearInterval(timer);
  }, [isPaused, slides.length]);

  if (!slides.length) return null;

  return (
    <div 
      className="relative w-full h-[50vh] md:h-[60vh] lg:h-[70vh] overflow-hidden mb-12 shadow-[0_30px_60px_rgba(0,0,0,0.8)]"
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
    >
      <AnimatePresence mode="wait">
        <motion.div
          key={current}
          initial={{ opacity: 0, scale: 1.05 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          className="absolute inset-0"
        >
          <img
            src={slides[current].bannerUrl}
            alt={slides[current].title}
            className="w-full h-full object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-l from-[#0e0e0e] via-[#0e0e0e]/80 to-transparent" />
          <div className="absolute inset-0 bg-gradient-to-t from-[#0e0e0e] via-transparent to-transparent" />
          
          <div className="absolute inset-0 flex flex-col justify-center px-8 md:px-16 lg:px-24 w-full md:w-2/3">
            <motion.h2 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3, duration: 0.6 }}
              className="text-4xl md:text-6xl font-black text-white leading-tight mb-4 drop-shadow-2xl"
              dir="auto"
            >
              {slides[current].title}
            </motion.h2>
            
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4, duration: 0.6 }}
              className="flex items-center gap-4 text-[#cccccc] font-semibold text-sm mb-6"
            >
              {slides[current].rating !== '--' && (
                <span className="text-green-400 border border-green-400/30 bg-green-400/10 px-2 py-0.5 rounded">
                  {slides[current].rating} MAL
                </span>
              )}
              {slides[current].type && <span className="bg-white/10 px-2 py-0.5 rounded">{slides[current].type}</span>}
            </motion.div>

            <motion.p 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5, duration: 0.6 }}
              className="text-[#aaaaaa] text-sm md:text-base line-clamp-3 max-w-xl mb-8 leading-relaxed"
              dir="auto"
            >
              {slides[current].desc}
            </motion.p>

            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6, duration: 0.6 }}
              className="flex items-center gap-4"
            >
              <Link 
                href={`/anime/${slides[current].slug}`}
                className="flex items-center gap-2 bg-white text-black px-8 py-3.5 font-bold hover:bg-white/90 transition-colors"
              >
                <Play className="w-5 h-5 fill-black" /> مشاهدة الآن
              </Link>
              <Link 
                href={`/anime/${slides[current].slug}`}
                className="flex items-center gap-2 bg-[#262626]/80 backdrop-blur-md text-white border border-white/10 px-8 py-3.5 font-bold hover:bg-[#333333]/80 transition-colors"
              >
                <Info className="w-5 h-5" /> التفاصيل
              </Link>
            </motion.div>
          </div>
        </motion.div>
      </AnimatePresence>

      <div className="absolute bottom-6 right-8 md:right-16 lg:right-24 flex gap-2 z-20">
        {slides.map((_, i) => (
          <button
            key={i}
            onClick={() => setCurrent(i)}
            className={`h-1.5  transition-all duration-300 ${i === current ? 'w-8 bg-white' : 'w-2 bg-white/30 hover:bg-white/50'}`}
          />
        ))}
      </div>
    </div>
  );
}
