'use client';
import Link from 'next/link';
import { Search } from 'lucide-react';
import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function Header() {
  const [query, setQuery] = useState('');
  const router = useRouter();

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      router.push(`/search?q=${encodeURIComponent(query.trim())}`);
    }
  };

  return (
    <header style={{
      position: 'sticky',
      top: 0,
      zIndex: 1000,
      backgroundColor: 'var(--header-bg)',
      backdropFilter: 'blur(20px)',
      borderBottom: '1px solid var(--border)',
      height: '56px',
      display: 'flex',
      alignItems: 'center'
    }}>
      <div className="container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', gap: '24px' }}>
        <Link href="/" style={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
          <span style={{ fontSize: '1.2rem', fontWeight: '800', letterSpacing: '-0.3px', color: '#000' }}>
            ANIME<span style={{ color: '#999' }}>SLAYER</span>
          </span>
        </Link>

        <form onSubmit={handleSearch} style={{ position: 'relative', maxWidth: '280px', width: '100%' }}>
          <input
            type="text"
            placeholder="Search..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{
              width: '100%',
              backgroundColor: '#f5f5f7',
              border: '1px solid transparent',
              borderRadius: '8px',
              padding: '7px 12px 7px 34px',
              color: '#000',
              fontSize: '13px',
              fontWeight: '500',
              outline: 'none',
              transition: 'all 0.2s'
            }}
          />
          <Search size={15} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#999' }} />
        </form>

        <nav style={{ display: 'flex', gap: '20px', marginLeft: 'auto' }}>
          <Link href="/" style={{ fontSize: '13px', fontWeight: '600', color: 'var(--foreground)' }}>Home</Link>
          <Link href="/?type=currently_airing" style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text-muted)' }}>Trending</Link>
          <Link href="/?type=top_tv" style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text-muted)' }}>Top Rated</Link>
        </nav>
      </div>
    </header>
  );
}
