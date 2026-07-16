import Link from 'next/link';
import { ChevronDown, Search } from 'lucide-react';
import Container from './Container';
import SearchOverlay from './SearchOverlay';
import ThemeToggle from './ThemeToggle';

export default function Header() {
  return (
    <header className="sticky top-0 z-50 w-full border-b-2 border-border bg-background">
      <Container>
        <div className="flex h-16 items-center justify-between">
          <div className="flex items-center gap-8">
            <Link href="/" className="flex items-center group">
              <span className="font-black text-2xl tracking-tighter text-foreground drop-shadow-sm transition-transform group-hover:scale-[1.02]">
                ANIME<span className="text-muted font-normal transition-colors group-hover:text-muted/80">BIND</span>
              </span>
            </Link>
            <nav className="hidden lg:flex items-center gap-6 text-[13px] font-bold tracking-wide">
              <Link href="/" className="text-muted hover:text-foreground transition-colors relative after:absolute after:-bottom-1 after:right-0 after:w-0 after:h-0.5 after:bg-foreground hover:after:w-full after:transition-all after:duration-300">
                الرئيسية
              </Link>
              <Link href="/all" className="text-muted hover:text-foreground transition-colors relative after:absolute after:-bottom-1 after:right-0 after:w-0 after:h-0.5 after:bg-foreground hover:after:w-full after:transition-all after:duration-300">
                كل الأنميات
              </Link>
              <Link href="/seasons" className="text-muted hover:text-foreground transition-colors relative after:absolute after:-bottom-1 after:right-0 after:w-0 after:h-0.5 after:bg-foreground hover:after:w-full after:transition-all after:duration-300">
                المواسم
              </Link>

              {/* Dropdown */}
              <div className="relative group py-5">
                <span className="cursor-pointer text-muted group-hover:text-foreground transition-colors flex items-center gap-1.5 relative after:absolute after:-bottom-1 after:right-0 after:w-0 after:h-0.5 after:bg-foreground group-hover:after:w-full after:transition-all after:duration-300">
                  التصنيفات
                  <ChevronDown className="w-3.5 h-3.5 transition-transform duration-300 group-hover:rotate-180" />
                </span>
                
                {/* Dropdown Menu */}
                <div className="absolute top-full right-0 w-64 bg-card border border-border shadow-[0_20px_40px_rgba(0,0,0,0.4)]
                  opacity-0 invisible translate-y-3 scale-95 origin-top-right
                  group-hover:opacity-100 group-hover:visible group-hover:translate-y-0 group-hover:scale-100
                  transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] overflow-hidden">
                  
                  {/* Rankings */}
                  <div className="px-5 pt-4 pb-2 text-[10px] font-black text-muted uppercase tracking-widest border-b border-border">
                    تقييم الموقع
                  </div>
                  <Link href="/top/top_anime" className="flex items-center gap-3 px-5 py-3 text-sm text-muted-fg hover:text-foreground hover:bg-border/30 transition-colors">
                    <span className="w-1.5 h-1.5 bg-foreground" />
                    أفضل الأنميات
                  </Link>
                  <Link href="/top/top_movie" className="flex items-center gap-3 px-5 py-3 text-sm text-muted-fg hover:text-foreground hover:bg-border/30 transition-colors">
                    <span className="w-1.5 h-1.5 bg-foreground/60 " />
                    أفضل الأفلام
                  </Link>
                  <Link href="/top/top_currently_airing" className="flex items-center gap-3 px-5 py-3 text-sm text-muted-fg hover:text-foreground hover:bg-border/30 transition-colors">
                    <span className="w-1.5 h-1.5 bg-foreground/40 " />
                    الأكثر مشاهدة
                  </Link>
                  <Link href="/top/top_upcoming" className="flex items-center gap-3 px-5 py-3 text-sm text-muted-fg hover:text-foreground hover:bg-border/30 transition-colors">
                    <span className="w-1.5 h-1.5 bg-foreground/20 " />
                    الأكثر توقعاً
                  </Link>

                  {/* MAL Rankings */}
                  <div className="px-5 pt-4 pb-2 text-[10px] font-black text-muted uppercase tracking-widest border-y border-border bg-background/50">
                    تصنيف MyAnimeList
                  </div>
                  <Link href="/top/top_anime_mal" className="flex items-center gap-3 px-5 py-3 text-sm text-muted-fg hover:text-foreground hover:bg-border/30 transition-colors">
                    <span className="w-1.5 h-1.5 bg-foreground" />
                    أفضل الأنميات (MAL)
                  </Link>
                  <Link href="/top/top_movie_mal" className="flex items-center gap-3 px-5 py-3 text-sm text-muted-fg hover:text-foreground hover:bg-border/30 transition-colors">
                    <span className="w-1.5 h-1.5 bg-foreground/60 " />
                    أفضل الأفلام (MAL)
                  </Link>
                  <Link href="/top/top_currently_airing_mal" className="flex items-center gap-3 px-5 py-3 text-sm text-muted-fg hover:text-foreground hover:bg-border/30 transition-colors">
                    <span className="w-1.5 h-1.5 bg-foreground/40 " />
                    الأكثر مشاهدة (MAL)
                  </Link>
                  <Link href="/top/top_tv_mal" className="flex items-center gap-3 px-5 py-3 text-sm text-muted-fg hover:text-foreground hover:bg-border/30 transition-colors">
                    <span className="w-1.5 h-1.5 bg-foreground/20 " />
                    أفضل المسلسلات (MAL)
                  </Link>
                </div>
              </div>

              <Link href="/schedule" className="text-muted hover:text-foreground transition-colors relative after:absolute after:-bottom-1 after:right-0 after:w-0 after:h-0.5 after:bg-foreground hover:after:w-full after:transition-all after:duration-300">
                مواعيد العرض
              </Link>
            </nav>
          </div>

          <div className="flex items-center gap-2">
            <SearchOverlay />
            <ThemeToggle />
          </div>
        </div>
      </Container>
    </header>
  );
}